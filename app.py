from flask import Flask, request
from flask import jsonify
import psycopg2
import os
from dotenv import load_dotenv
from process import tracker
load_dotenv(".env")
DB_SERVER = os.getenv('DB_SERVER')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_DATABASE = os.getenv('DB_DATABASE')
DB_PORT = os.getenv('DB_PORT')
TMP_DIR = os.getenv('TMP_DIR')
if not TMP_DIR:
    TMP_DIR = 'tmp'

app = Flask(__name__)

#ответ сервера если пользователь ничего не передал
@app.route("/", methods=["GET"])
def hello():
    return "Hello World!"


#Форма для проверки модели машинного обучения (загрузка файла с картинкой и отправка запроса)
@app.route('/product/scanform', methods=['GET', 'POST'])
def productScanForm():
    form="""
    <!doctype html>
    <title>Загрузить новый файл</title>
    <h1>Загрузить новый файл</h1>
    <form method=post enctype=multipart/form-data action='/product/scantest'>
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
    </html>    
    
    """
    return form

#Функция для проверки нейронки
@app.route('/product/scantest', methods=['GET', 'POST'])
def productScanTest():
    if request.method == 'POST':
        print("Получили запрос на сканирование")

        request_files = request.files
        if not request_files:
            print('Нет файлов в запросе')
            return 500
        try:
            request_file = request.files['file']
        except:
            print('Не могу забрать файл из запроса')
            return 500
        # создаем временную директорию для файлов
        if not os.path.exists(TMP_DIR+'/upload'):
            os.makedirs(TMP_DIR+'/upload')
        filePath = TMP_DIR+"/img.jpg"
        # сохраняем файл
        request_file.save(filePath)
        print("Сохранили файл")

        productMLName = tracker(filePath)
        #удаляем файл, чтобы не засорять сервер
        os.remove(filePath)

        #получаем название продукта
        try:
            conn = psycopg2.connect(database=DB_DATABASE,
                                    host=DB_SERVER,
                                    user=DB_USER,
                                    password=DB_PASSWORD,
                                    port=DB_PORT)
        except:
            print("Не могу установить соединение с базой данных")
            return 500
        cursor = conn.cursor()
        query = ("SELECT name FROM product_names WHERE id_productname="+str(productMLName))
        cursor.execute(query)
        res = cursor.fetchone()
        if res:
            productName = res[0]
            print("Название выбранного продукта: ",productName)
        else:
            print("Продукт с выбранным номером не найден в справочнике")
            return 500

        return """
            <!doctype html>
            <title>Распознавание ценника</title>
            <h1>Распознавание ценника</h1>
            <р>Нейронка распознала продукт, это:</p>
            """+"<p>Номер продукта:"+str(productMLName)+", название продукта: "+productName+"</html>"
    else:
        print("Некорректный запрос, должен быть POST")
        return 500


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000)