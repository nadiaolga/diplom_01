import json
import os
import requests
from dotenv import load_dotenv


# Класс для работы c сервисом Ipify
class IpifyService:

    def __init__(self):
        self.base_url = "https://api.ipify.org?format=json"

    # Получаем текущий IP
    def get_my_ip(self) -> str:
        response = requests.get(self.base_url)
        response.raise_for_status()
        return response.json().get("ip")


# Класс для работы с сервисом ipinfo (получение города по IP)
# Иногда работает без токена, иногда не работает
class IpInfoService:

    def __init__(self):
        self.TOKEN_IPINFO = os.getenv("IPINFO_TOKEN")

        if not self.TOKEN_IPINFO:
            raise RuntimeError("Нет токена сервиса IPINFO")

    def get_location_by_ip(self, ip_address: str) -> dict:
        try:
            url = f"https://ipinfo.io/{ip_address}/geo"
            headers = {"Authorization": f"Bearer {self.TOKEN_IPINFO}"}

            response = requests.get(url, headers=headers)
            response.raise_for_status()

            geo_data = response.json()
            # Защита от пустых значений или отсутствия ключа "city"
            geo_data["city"] = geo_data.get("city") or "Неизвестный город"

            return geo_data

        except requests.exceptions.HTTPError as err:
            # Обрабатываем ошибки именно этого сервиса
            if err.response.status_code == 401:
                raise Exception("Ошибка IPInfo: Неверный токен авторизации.")
            elif err.response.status_code == 429:
                raise Exception("Ошибка IPInfo: Превышен лимит запросов (дневной или месячный).")
            else:
                raise Exception(f"Сетевая ошибка при запросе к IPInfo: {err}")

        except requests.exceptions.JSONDecodeError:
            raise Exception("Ошибка IPInfo: Сервер вернул некорректный JSON/HTML.")

        except requests.exceptions.RequestException as err:
            raise Exception(f"Произошла сетевая ошибка при получении геокоординат: {err}")


# Класс для управления файлами на Яндекс.Диске через REST API
class YandexDiskUploader:

    def __init__(self):
        self.TOKEN_YANDEX_DISK = os.getenv("YANDEX_DISK_TOKEN")
        self.base_url = "https://cloud-api.yandex.net"
        self.headers = {
            "Authorization": f"OAuth {self.TOKEN_YANDEX_DISK}",
            "Content-Type": "application/json"
        }
        if not self.TOKEN_YANDEX_DISK:
            raise RuntimeError("Нет токена сервиса YANDEX_DISK")

    # Создаем новую папку на Яндекс.Диске, если её еще нет
    def create_folder(self, folder_name: str) -> bool:
        params = {"path": folder_name}

        try:
            response = requests.put(f'{self.base_url}/v1/disk/resources', headers=self.headers, params=params)
            if response.status_code == 409:
                print(f'4. Папка {folder_name} уже существует.')
                return True # Папка уже есть, это не ошибка
            response.raise_for_status()
            if response.status_code == 201:
                print(f'4. Папка {folder_name} успешно создана' )
                return True
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 401:
                raise Exception("Ошибка Я.Диска: Неверный токен авторизации (OAuth).")
            elif err.response.status_code == 403:
                raise Exception("Ошибка Я.Диска: Закончилось место или нет прав доступа.")
            else:
                raise Exception(f"Ошибка при создании папки на Я.Диске: {err}")

    # Запрашиваем ссылку для загрузки, метод нужен для внутренней функции, поэтому приватный
    def _get_upload_link(self, disk_file_path: str) -> str:
        upload_url = f"{self.base_url}/v1/disk/resources/upload"
        params = {"path": disk_file_path, "overwrite": "true"}

        try:
            response = requests.get(upload_url, headers=self.headers, params=params)
            response.raise_for_status()
            print(f'5. Получили временную ссылку для загрузки.')
            return response.json().get("href")
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 401:
                raise Exception("Ошибка Я.Диска: Неверный токен авторизации.")
            raise Exception(f"Не удалось получить ссылку для загрузки: {err}")

    # Основной метод: создает папку, запрашивает ссылку и загружает файл.
    def upload_file(self, local_file_path: str, disk_folder: str):

        if not os.path.exists(local_file_path):
            raise Exception(f"Локальный файл '{local_file_path}' не найден!")

        file_name = os.path.basename(local_file_path)
        disk_file_path = f"{disk_folder}/{file_name}"

        # 1. Гарантируем наличие папки (универсально для будущих возможностей)
        self.create_folder(disk_folder)

        # 2. Получаем временную ссылку для загрузки
        upload_link = self._get_upload_link(disk_file_path)

        # 3. Отправляем байты файла напрямую в хранилище
        try:
            with open(local_file_path, "rb") as f:
                # Переопределяем Content-Type на бинарный поток специально для загрузки файла
                file_headers = {"Content-Type": "application/octet-stream"}
                response = requests.put(upload_link, data=f, headers=file_headers)
                response.raise_for_status()
                print(f'6. Загрузили файл на Яндекс.Диск.')
        except requests.exceptions.HTTPError as err:
            raise Exception(f"Ошибка при передаче данных на сервер Яндекса: {err}")



def main():

    OUTPUT_FILE = "geo_data.json"
    DISK_FOLDER = "IpDetector"
    load_dotenv()

    print("Запуск программы...")

    try:
        # Шаг 1: Работа с ipify
        ipify = IpifyService()
        current_ip = ipify.get_my_ip()
        print(f"1. Ваш внешний IP-адрес успешно определен: {current_ip}")

        # Шаг 2: Работа с ipinfo
        ipinfo = IpInfoService()
        geo_data = ipinfo.get_location_by_ip(current_ip)
        print(f"2. Данные о геолокации получены. Город: {geo_data['city']}")

        # Шаг 3: Сохранение в локальный JSON-файл
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(geo_data, f, ensure_ascii=False, indent=4)
        print(f"3. Данные успешно сериализованы в локальный файл '{OUTPUT_FILE}'")

        # Загрузка на Яндекс.Диск
        uploader = YandexDiskUploader()

        # # Шаг 4: Создание папки.
        # uploader.create_folder(DISK_FOLDER)

        # Шаги 4, 5 и 6: Создание папки, получение временной ссылки и загрузка файла.
        uploader.upload_file(local_file_path=OUTPUT_FILE, disk_folder=DISK_FOLDER)

    except requests.exceptions.HTTPError as http_err:
        print(f"\n Ошибка сети при запросе: {http_err}")
    except Exception as err:
        print(f"\n Произошла ошибка: {err}")

    finally:
        # Шаг 7: Очищаем диск
        if os.path.exists(OUTPUT_FILE):
            os.remove(OUTPUT_FILE)
            print(f"7. Очистка: Локальный файл '{OUTPUT_FILE}' успешно удален с компьютера.")


if __name__ == "__main__":
    main()