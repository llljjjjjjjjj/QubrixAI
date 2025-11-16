Инструмент для автоматической проверки строительных pdf документов. Он находит три вещи на страницах: подписи, печати и qr коды. Работает локально, а распознавание делает Gemini Vision через Google Gen AI SDK.

стек:
backend на python, обычный flask, opencv, pdf2image, matplotlib.
ai часть через google genai sdk. модель по умолчанию тут стоит gemini-2.5-flash.
frontend обычный html css и немного js с drag and drop загрузкой.

нужно перед запуском:
нужен python 3.
для корректной работы с pdf и qr нужно поставить системные пакеты:
macos:
brew install poppler zbar
ubuntu:
sudo apt-get install poppler-utils libzbar0
python зависимости потом ставятся из файла requirements.txt.

как установить и запустить
скачать или клонировать проект:
git clone <repo-url>
cd QubrixAI
создать виртуальное окружение и включить его:
python -m venv venv
source venv/bin/activate     # macos linux
venv\Scripts\activate        # windows
поставить зависимости:
pip install -r requirements.txt
настройка gemini
сервер использует ключ из переменных окружения. самая простая настройка:
export GOOGLE_API_KEY="ВАШ_КЛЮЧ" или
export GEMINI_API_KEY="ВАШ_КЛЮЧ"
затем GEMINI_MODEL_ID="gemini-2.5-flash"
если ключа нет, сервер поднимется, просто распознавания не будет, страницы отрисуются без рамок.

запуск из корня:
python server.py
сервер появится на
http://localhost:5000
все файлы интерфейса (index.html, styles.css, script.js) лежат рядом с server.py, flask их сам отдает.

как пользоваться:
открываете браузер, заходите по адресу выше.
перетаскиваете pdf или zip с pdf файлами в область загрузки (или выбираете через кнопку).нажимаете кнопку Run QubrixAI analysis и ждете.
в результате получите:
мини превью документов
статистику по страницам и количеству объектов
диаграмму распределения
просмотр аннотированных страниц в удобном окне
выгрузку json результатов
и аннотированный pdf для каждого документа
все промежуточные данные складываются в папку jobs. для каждой обработки создается отдельная папка с уникальным job_id.