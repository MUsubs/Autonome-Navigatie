from flask import Flask, request, jsonify, render_template, redirect, url_for
import serial
import time
import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'include'))
from SerialControl import SerialControl
from db import get_db, close_db, init_db, init_db_command, init_app

# PLACEHOLDER FUNCTION
def read_current_location():
    return 0.1, 0.2, 0.3

def create_app(clear_database=True):
    app = Flask(__name__)
    database_path = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(app.instance_path)), r'include\flaskr.sqlite'))
    print(database_path)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=database_path,
    )
    server = Server(app, clear_database)
    return app

class Server:
    def __init__(self, app, clear_database=False):
        print("Constructor called")
        self.ser = serial.Serial()
        self.app = app
        self.configure_routes()
        self.server_serial = SerialControl()
        if clear_database:
            print("Clear database was True")
            init_app(self.app, True)


    def configure_routes(self):
        @self.app.route('/')
        def index():
            return render_template('index.html')

        @self.app.route('/coordinates', methods=['GET', 'POST'])
        def coordinates():
            if request.method == 'POST':
                try:
                    num_values = int(request.form['num_values'])
                    return redirect(url_for('input_coordinates', num_values=num_values))
                except ValueError:
                    return jsonify(success=False, message="Invalid input for number of values"), 400
            return render_template('coordinates.html')

        @self.app.route('/input_coordinates/<int:num_values>', methods=['GET', 'POST'])
        def input_coordinates(num_values):
            if request.method == 'POST':
                db = get_db()
                coordinates = []
                for i in range(num_values):
                    try:
                        x = float(request.form[f'x_{i}'])
                        y = float(request.form[f'y_{i}'])
                        z = float(request.form[f'z_{i}'])
                        coordinates.append((x, y, z))
                    except ValueError:
                        return jsonify(success=False, message="Invalid input for coordinates"), 400

                for coord in coordinates:
                    try:
                         db.execute(
                    "INSERT INTO target_destinations (x, y, z) VALUES (?, ?, ?)",
                    (coord[0], coord[1], coord[2]),
                )   
                         db.commit()  
                         print("Values inserted into database")
                    except db.IntegrityError:
                        error = f"Coordinates {coord[0], coord[1], coord[2]} error"
                    self.server_serial.send_serial(f'INST,X={coord[0]},Y={coord[1]},Z={coord[2]}', 8)
                return redirect(url_for('send_current_location'))
            
            return render_template('input_coordinates.html', num_values=num_values)

        @self.app.route('/data')
        def data():
            sensor_data_path = f'{os.getcwd()}\desktop\include\sensordata.json'
            if not os.path.exists(sensor_data_path):
                print(f"File not found: {sensor_data_path}, Current CWD: {os.getcwd()}")
                return jsonify(success=False, message="Sensor data file not found"), 404
            
            try:
                with open(sensor_data_path, 'r') as f:
                    sensor_data = json.load(f)
            except FileNotFoundError:
                return jsonify(success=False, message="Sensor data file not found"), 404
            return render_template('data.html', sensor_data=sensor_data)
        
        @self.app.route('/send_current_location')
        def send_current_location():
            x, y, z = read_current_location()
            serial_response = self.server_serial.send_serial(f"UPDATE,CURR,X{x},Y{y},Z{z}", 8)
            if serial_response != 0:
                db = get_db()
                label, value = serial_response.split(',')
                temperature_value = float(value.strip())
                print(temperature_value)
                try:
                    db.execute(
                "INSERT INTO temperature (temperature_value) VALUES (?)",
                (temperature_value,),
                )   
                    db.commit()  
                    print("Values inserted into database")
                except db.IntegrityError:
                        error = f"Temperature {temperature_value} error"
            return render_template('send_current_location.html', x=x, y=y, z=z)

    
    def run(self, debug=True, use_reloader=False):
        self.app.run(debug=debug, use_reloader=use_reloader)

