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

@app.route("/", methods=["GET"])
def hello():
    return "Hello World!"


@app.route('/product/scanform', methods=['GET', 'POST'])
def productScanForm():
    form="""
    <!doctype html>
    <title>File upload</title>
    <h1>Upload the new file</h1>
    <form method=post enctype=multipart/form-data action='/product/scantest'>
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
    </html>    
    
    """
    return form

@app.route('/product/scantest', methods=['GET', 'POST'])
def productScanTest():
    if request.method == 'POST':
        print("New scan request")

        request_files = request.files
        if not request_files:
            print('No files')
            return 500
        try:
            request_file = request.files['file']
        except:
            print('Cannott get a file from the request')
            return 500
        if not os.path.exists(TMP_DIR+'/upload'):
            os.makedirs(TMP_DIR+'/upload')
        filePath = TMP_DIR+"/img.jpg"
        request_file.save(filePath)
        print("File is saved")

        productMLName = tracker(filePath)
        os.remove(filePath)

        try:
            conn = psycopg2.connect(database=DB_DATABASE,
                                    host=DB_SERVER,
                                    user=DB_USER,
                                    password=DB_PASSWORD,
                                    port=DB_PORT)
        except:
            print("Database is not available")
            return 500
        cursor = conn.cursor()
        query = ("SELECT name FROM product_names WHERE id_productname="+str(productMLName))
        cursor.execute(query)
        res = cursor.fetchone()
        if res:
            productName = res[0]
            print("Product name: ",productName)
        else:
            print("Product is not found")
            return 500

        return """
            <!doctype html>
            <title>Image recognition</title>
            <h1>Studying the image</h1>
            <р>The product is found:</p>
            """+"<p>Product munber:"+str(productMLName)+", name: "+productName+"</html>"
    else:
        print("The request is incorrect, should be POST")
        return 500


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000)