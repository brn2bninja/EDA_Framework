import os
import psycopg2
from flask import Flask, request, Response, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import uuid
#from model import orion
import json
import pandas as pd
from typing import Dict, Any, Union
import pickle
from sqlalchemy import create_engine

metric_tables = ['bgwriter', 'access', 'io', 'os_metric', 'sessions', 'active_sessions', 'waiting_sessions', 'database_statistics', 'conflicts', 'query_statistics','performance']
non_default_table = ['sessions', 'active_sessions', 'waiting_sessions','query_statistics']
derived_metric_tables = ['load_prediction', 'anomaly_time_interval', 'anomaly_scorer', 'anomaly_detector']
db_statistics_tables = ['database_statistics', 'conflicts']
datasets = ['dbsherlock']

"""
The main entrypoint for the driver. The driver will poll for new configurations and schedule
executions of monitoring and tuning pipeline.
"""
import logging

from apscheduler.schedulers.background import BlockingScheduler

from driver.pipeline import (
    schedule_or_update_job,
    DB_LEVEL_MONITOR_JOB_ID,
    TABLE_LEVEL_MONITOR_JOB_ID,
)

# Setup the scheduler that will poll for new configs and run the core pipeline
scheduler = BlockingScheduler(daemon = True, job_defaults={'max_instances': 20})

with open('../port.json', 'r') as json_file:
    data = json.load(json_file)
    server_db_port = data.get('serverdb')
    server_port = data.get('server')

# Replace the placeholder values with your actual database connection details
server_engine = create_engine(f'postgresql://postgres:postgres@localhost:{server_db_port}/dbeda')


server_conn = psycopg2.connect(
        host='localhost',
        database='dbeda',
        user='postgres',
        password='postgres',
        port=server_db_port,
    )

def schedule_db_level_monitor_job(config, db_id) -> None:
    """
    The outer polling loop for the driver
    """
    schedule_or_update_job(scheduler, config, DB_LEVEL_MONITOR_JOB_ID, db_id)


def schedule_table_level_monitor_job(config) -> None:
    """
    The polling loop for table level statistics
    """
    schedule_or_update_job(scheduler, config, TABLE_LEVEL_MONITOR_JOB_ID)

app = Flask(__name__)
scheduler = BackgroundScheduler()

@app.route('/connect', methods=['POST'])
def connect_user_database():
    # Get database configuration data from the client request
    data = request.get_json()
    db_type = data['db_type']
    db_host = data['db_host']
    db_port = data['db_port']
    db_name = data['db_name']
    db_user = data['db_user']
    db_password = data['db_password']
    
    
    
    # Add collect_metrics function to the scheduler
    # Check if the input DB configuration already exists in the database
    cur = server_conn.cursor()
    cur.execute("""
        SELECT id
        FROM db_config
        WHERE db_type = %s AND db_host = %s AND db_port = %s AND db_name = %s AND db_user = %s;
    """, (db_type, db_host, db_port, db_name, db_user))
    result = cur.fetchone()

    if result:
        # If the input DB configuration already exists in the database, use the existing ID
        db_id = result[0]
    else:
        # If the input DB configuration does not exist in the database, generate a new ID
        db_id = str(uuid.uuid4())
        #print(db_id, db_type, db_host, db_port, db_name, db_user, db_password)
        # Store the new DB ID and configuration in the database
        cur.execute("""
            INSERT INTO db_config (id, db_type, db_host, db_port, db_name, db_user, db_password)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """, (db_id, db_type, db_host, db_port, db_name, db_user, db_password))
        server_conn.commit()

    # Return a success response
    return f"{db_id}Database configuration data received successfully!"


@app.route('/collect', methods=['POST'])
def collect_performance_data():
    # Get database configuration data from the client request
    data = request.get_json()
    db_type = data['db_type']
    db_host = data['db_host']
    db_port = data['db_port']
    db_name = data['db_name']
    db_user = data['db_user']
    db_password = data['db_password']
    
    # Add collect_metrics function to the scheduler
    # Check if the input DB configuration already exists in the database
    cur = server_conn.cursor()
    cur.execute("""
        SELECT id
        FROM db_config
        WHERE db_type = %s AND db_host = %s AND db_port = %s AND db_name = %s AND db_user = %s AND db_password = %s;
    """, (db_type, db_host, db_port, db_name, db_user, db_password))
    result = cur.fetchone()

    if result:
        # If the input DB configuration already exists in the database, use the existing ID
        db_id = result[0]
    else:
        # If the input DB configuration does not exist in the database, generate a new ID
        db_id = str(uuid.uuid4())
        #print(db_id, db_type, db_host, db_port, db_name, db_user, db_password)
        # Store the new DB ID and configuration in the database
        cur.execute("""
            INSERT INTO db_config (id, db_type, db_host, db_port, db_name, db_user, db_password)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """, (db_id, db_type, db_host, db_port, db_name, db_user, db_password))
        server_conn.commit()

    # Return the DB ID to the client
    collect_metrics(db_id, db_type, db_host, db_port, db_name, db_user, db_password)

    # Return a success response
    return f"{db_id}Database configuration data received successfully!"

def get_dbid(config):
    
    cur = server_conn.cursor()
    cur.execute("""
        SELECT id
        FROM db_config
        WHERE db_type = %s AND db_host = %s AND db_port = %s AND db_name = %s AND db_user = %s;
    """, (config['db_type'],config['db_host'], config['db_port'], config['db_name'], config['db_user']))
    result = cur.fetchone()

    if result:
        # If the input DB configuration already exists in the database, use the existing ID
        db_id = result[0]
    else:
        raise KeyError("Cannot find database configuration. Connect is first.")
    
    return db_id
        
def collect_metrics(db_id, db_type, db_host, db_port, db_name, db_user, db_password):
    driver_config = {
        "db_host":db_host,
        "db_port":db_port,
        "db_name":db_name,
        "db_user":db_user,
        "db_password":db_password,
        "db_type":"postgres",
        "monitor_interval":"6",
        "table_level_monitor_interval":"5000",
        "db_provider": "on_premise",
        "db_key": "test_key",
        "organization_id": "test_organization"
    }
    schedule_db_level_monitor_job(driver_config, db_id)
    scheduler.start()
    # Run queries to collect metrics and store them in a file or database

def preprocess_dataframe(df, interval):
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    # Resample the data to 10-minute intervals and calculate the mean

    if 'analysis_time' in df.columns:
        df_resampled = df.groupby('analysis_time').resample(f'{interval}S').mean()
    else:
        df_resampled = df.resample(f'{interval}S').mean()

    df_resampled.reset_index(inplace = True)
    df_resampled.fillna(method='ffill', inplace=True)
    return df_resampled


@app.route('/data', methods=['GET'])
def perform_data_query():
    params_json = request.args.get('params')
    args = json.loads(params_json)

    table = args['table']
    metrics = args['metric']
    if 'start_time' in args:
        start_time = args['start_time']
        end_time = args['end_time']
    recent_time_window = args['recent_time_window']
    task = args['task']
    if 'order' in args:
        order = args['order']
        num_of_query = int(args['num_of_query'])

    if task == 'anomaly analysis':
        task = args['task_type']
    
    if 'analysis_time' in args:
        analysis_time = args['analysis_time']

    db_id = get_dbid(args['config'])
    collect_interval = args['config']['interval']
    

    data = {}

    # fetch metric data
    if task == 'anomaly detection and explanation' or task == 'anomaly analysis':
        if metrics == 'all':
            sql_query = f"""SELECT * FROM {table} """
            sql_query += f"""ORDER BY timestamp ASC;"""
            df_metrics = pd.read_sql_query(sql_query, server_engine)
            # df_metrics = preprocess_dataframe(df_metrics, collect_interval)
            df_metrics['timestamp'] = df_metrics['timestamp'].astype(str)
        
    else:
        if type(metrics) == str:
            metric_string = metrics
        else:
            metric_string = ', '.join(metrics)
        # SQL 쿼리문 작성
        sql_query = ''
        
        # Select From
        if metrics == 'all':
            sql_query += f"""SELECT * FROM {table} """  
        else:
            sql_query += f"""SELECT timestamp, {metric_string} FROM {table} """

        # Where
        if recent_time_window == 'Custom':
            sql_query += f"""WHERE timestamp BETWEEN '{start_time}' AND '{end_time}'
                            AND dbid = '{db_id}'
                            ORDER BY timestamp ASC;"""
        elif recent_time_window == 'All':
            if table in datasets:
                sql_query += f"""ORDER BY timestamp ASC;"""
            else:
                sql_query += f"""WHERE dbid = '{db_id}'
                                ORDER BY timestamp ASC;"""
        else:
            sql_query += f"""WHERE timestamp >= NOW() - INTERVAL '{recent_time_window}'
                            AND dbid = '{db_id}'
                            ORDER BY timestamp ASC;"""


        df_metrics = pd.read_sql_query(sql_query, server_engine)
        print(sql_query)
        print(df_metrics)
        df_metrics = preprocess_dataframe(df_metrics, collect_interval)
        df_metrics['timestamp'] = df_metrics['timestamp'].astype(str)
        
    if task == 'timeseries analysis':
        data['metric'] = df_metrics.to_dict()
       
        return json.dumps(data)
    elif task == 'query ranking':
        sql_query = f"""SELECT timestamp, {metric_string}, queryid, query FROM query_statistics """
        
        if recent_time_window == 'Custom':
            sql_query += f"""WHERE timestamp BETWEEN '{start_time}' AND '{end_time}'
                            AND dbid = '{db_id}'
                            ORDER BY timestamp ASC;"""
        else:
            sql_query += f"""WHERE timestamp BETWEEN (NOW() - INTERVAL '{recent_time_window}') AND NOW()
                            AND dbid = '{db_id}'
                            ORDER BY timestamp ASC;"""
    
        df_task = pd.read_sql_query(sql_query, server_engine)

        query_dict = dict(zip(df_task['queryid'], df_task['query']))
        data['query_dict'] = query_dict

        ascending = False
        if order == "ASC":
            ascending = True
        df_task = df_task.groupby('queryid').sum().sort_values(by=metric_string, ascending=ascending).iloc[:num_of_query]        
        
    elif task == 'query analysis':
        sql_query = f"""SELECT timestamp, {metric_string}, queryid, query FROM query_statistics """
        
        if recent_time_window == 'Custom':
            sql_query += f"""WHERE timestamp BETWEEN '{start_time}' AND '{end_time}'
                            AND dbid = '{db_id}'
                            ORDER BY timestamp ASC;"""
        else:
            sql_query += f"""WHERE timestamp BETWEEN (NOW() - INTERVAL '{recent_time_window}') AND NOW()
                            AND dbid = '{db_id}'
                            ORDER BY timestamp ASC;"""
        df_task = pd.read_sql_query(sql_query, server_engine)

        query_dict = dict(zip(df_task['queryid'], df_task['query']))
        data['query_dict'] = query_dict

        ascending = True
        if order == "DESC":
            ascending = False
        slice_df = df_task.groupby('queryid').sum().sort_values(by=metric_string, ascending=ascending).iloc[:num_of_query]
        top_queryid = slice_df.index.tolist() # 문제    
        mask = df_task['queryid'].isin(top_queryid)
        data['top_queryid'] = top_queryid
        df_task = df_task[mask]

       
    elif task == 'load prediction':
        
        data['metric'] = df_metrics.to_dict()
       
        sql_query = f"""SELECT timestamp, predicted, lower_bound, upper_bound, analysis_time FROM load_prediction """
        
        if recent_time_window == 'Custom':
            sql_query += f"""WHERE timestamp >= '{start_time}'
                            AND dbid = '{db_id}'
                            AND metric = '{metric_string}'
                            ORDER BY timestamp ASC;"""
                            #  f"""WHERE timestamp BETWEEN '{start_time}' AND '{end_time}'
                            # AND dbid = '{db_id}'
                            # AND metric = '{metric_string}'
                            # ORDER BY timestamp ASC;"""
        else:
            sql_query += f"""WHERE timestamp >= (NOW() - INTERVAL '{recent_time_window}') 
                            AND dbid = '{db_id}'
                            AND metric = '{metric_string}'
                            ORDER BY timestamp ASC;"""

        df_task = pd.read_sql_query(sql_query, server_engine)
        df_task = preprocess_dataframe(df_task, collect_interval)

        
    elif task == 'anomaly time interval':
        assert len(metrics) == 1

        data['metric'] = df_metrics.to_dict()

        sql_query = f"""SELECT analysis_time, start, end, severity FROM anomaly_time_interval"""
        
        if recent_time_window == 'Custom':
            sql_query += f"""WHERE timestamp BETWEEN '{start_time}' AND '{end_time}'
                            AND dbid = '{db_id}'
                            AND (metric = '{metric_string}' OR metric IS NULL)
                            ORDER BY timestamp ASC;"""
        else:
            sql_query += f"""WHERE timestamp BETWEEN NOW() - INTERVAL '{recent_time_window}' AND NOW()
                            AND dbid = '{db_id}'
                            AND metric = '{metric_string}'
                            ORDER BY timestamp ASC;"""

        df_task = pd.read_sql_query(sql_query, server_engine)
    elif task == 'anomaly scorer':
        
        data['metric'] = df_metrics.to_dict()
        sql_query = f"""SELECT timestamp, anomaly_score, analysis_time FROM anomaly_scorer """
        if recent_time_window == 'Custom':
            sql_query += f"""WHERE timestamp BETWEEN '{start_time}' AND '{end_time}'
                            AND dbid = '{db_id}'
                            AND (metric = '{metric_string}' OR metric IS NULL)
                            ORDER BY timestamp ASC;"""
        else:
            sql_query += f"""WHERE timestamp BETWEEN NOW() - INTERVAL '{recent_time_window}' AND NOW()
                            AND dbid = '{db_id}'
                            AND metric = '{metric_string}'
                            ORDER BY timestamp ASC;"""

        df_task = pd.read_sql_query(sql_query, server_engine)
        df_task = preprocess_dataframe(df_task, collect_interval)
    elif task == 'anomaly detection and explanation':
        data['metric'] = df_metrics.to_dict()

        sql_query = f"""SELECT timestamp, anomaly_score, is_anomaly, anomaly_cause, analysis_time FROM anomaly_explanation """
        sql_query += f"""WHERE dbid = '{db_id}' """
        if 'analysis_time' in args and analysis_time != '':
            sql_query += f""" and analysis_time = '{analysis_time}'"""

        sql_query += """ORDER BY timestamp ASC;"""
        df_task = pd.read_sql_query(sql_query, server_engine)

    
    if 'timestamp' in df_task:
        df_task['timestamp'] = df_task['timestamp'].astype(str)
    if 'analysis_time' in df_task:
        df_task['analysis_time'] = df_task['analysis_time'].astype(str)
    data['task'] = df_task.to_dict()    
    return json.dumps(data)


@app.route('/analysis_time', methods=['GET'])
def get_analysis_time():
    params_json = request.args.get('params')
    args = json.loads(params_json)

    table = args['table']
    db_id = get_dbid(args['config'])

    sql_query = f'SELECT DISTINCT analysis_time from {table}'
    result_df = pd.read_sql_query(sql_query, server_engine)
    result = result_df['analysis_time'].astype(str)
    print(result_df)
    response = {}
    response['analysis_time'] = list(result)
    print(response['analysis_time'])
    return json.dumps(response)



@app.route('/schema', methods=['GET'])
def get_schema():
    
    config = request.args.to_dict()
    db_id = get_dbid(config)
    # 커서 생성
    cur = server_conn.cursor()
    schema = {}
    # 모든 테이블 가져오기
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_catalog = 'dbeda' 
        AND table_schema = 'public' 
        AND table_type = 'BASE TABLE'
    """)

    # 결과 가져오기
    rows = cur.fetchall()

    result = pd.DataFrame(columns=['table','column','type','key'])
    # dbid 열의 값이 db_id인 테이블들 찾기
    for row in rows:
        table_name = row[0]
        if table_name == 'db_config':
            continue
        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}'")
        table_columns = cur.fetchall()
        if len(table_columns) <= 2:
            continue
        # primary key 확인
        cur.execute(f"""
            SELECT CC.COLUMN_NAME AS COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS       TC
                ,INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE CC
            WHERE TC.TABLE_CATALOG   = 'dbeda'
            AND TC.TABLE_NAME      = '{table_name}'
            AND TC.CONSTRAINT_TYPE = 'PRIMARY KEY'
            AND TC.TABLE_CATALOG   = CC.TABLE_CATALOG
            AND TC.TABLE_SCHEMA    = CC.TABLE_SCHEMA
            AND TC.TABLE_NAME      = CC.TABLE_NAME
            AND TC.CONSTRAINT_NAME = CC.CONSTRAINT_NAME
            ;
        """)
        primary_key_columns = cur.fetchall()

        if 'dbid' in [column[0] for column in table_columns]:
            cur.execute(f"SELECT * FROM public.{table_name} WHERE dbid = '{db_id}'") 
            if cur.fetchone():
                for column in table_columns:
                    key = False
                    if column in primary_key_columns:
                        key = True
                    new_df = pd.DataFrame({'table': [table_name], 'column':[column[0]], 'type':[column[1]], 'key':[key]})
                    result = pd.concat([result, new_df],ignore_index=True)
                schema[table_name] = table_columns
        
        elif table_name in datasets:
            cur.execute(f"SELECT * FROM public.{table_name}")
            if cur.fetchone():
                for column in table_columns:
                    key = False
                    if column in primary_key_columns:
                        key = True
                    new_df = pd.DataFrame({'table': [table_name], 'column':[column[0]], 'type':[column[1]], 'key':[key]})
                    result = pd.concat([result, new_df],ignore_index=True)
                schema[table_name] = table_columns
            print(schema[table_name])


    # 커서와 연결 닫기
    cur.close()
    response = {}
    response['sidebar_content'] = result.to_dict()
    response['schema'] =  schema
    return json.dumps(response)


@app.route('/all_metrics', methods=['GET'])
def fetch_metrics_within_time_range(config=None, start_time='-infinity', end_time='infinity'):
    if request.args:
        params_json = request.args.get('params')
        args = json.loads(params_json)
        config = args['config']
        if 'start_time' in args:
            start_time = args['start_time']
            end_time = args['end_time']
    
    db_id = get_dbid(config)

    # 조회된 결과를 저장할 빈 DataFrame 생성
    result_df = pd.DataFrame()

    # DB 쿼리문
    db_statistics_query = """
    SELECT 
        timestamp, {} 
    FROM 
        {} 
    WHERE 
        dbid = %s
    AND timestamp BETWEEN '{}' AND '{}'
    GROUP BY timestamp;
    """

    # 모든 컬럼 이름 가져오기
    columns_query = """
    SELECT 
        COLUMN_NAME 
    FROM 
        INFORMATION_SCHEMA.COLUMNS 
    WHERE 
        TABLE_NAME = '{}' ;
    """
    
    cur = server_conn.cursor()
    # metric table들을 순회하며 조회 쿼리를 실행하고 결과를 DataFrame에 추가
    for table_name in metric_tables:
        if table_name in db_statistics_tables:
            continue
            cur.execute(columns_query.format(table_name))
            column_names = [row[0] for row in cur.fetchall()]
            column_names = [col for col in column_names if col not in ['timestamp', 'dbid', 'datid','datname']]
            
            # 컬럼들의 합을 계산하고 datid로 groupby
            query = db_statistics_query.format(", ".join(["SUM({}) AS {}".format(col, col) for col in column_names]), table_name, start_time, end_time)
        elif table_name in non_default_table:
            continue
        else:
            cur.execute(columns_query.format(table_name))
            column_names = [row[0] for row in cur.fetchall()]
            column_names = [col for col in column_names if col not in ['timestamp', 'dbid', 'datid','datname']]
            if len(column_names) == 0:
                continue
            query = f"""
                SELECT timestamp, {", ".join([col for col in column_names])}
                FROM {table_name}
                WHERE dbid = %s
            """
            if start_time is not None and end_time is not None:
                query += f"AND timestamp BETWEEN '{start_time}' AND '{end_time}'"
        print(query)
        cur.execute(query, (db_id,))
        results = cur.fetchall()

        temp_df = pd.DataFrame(results, columns=['timestamp'] + column_names)
        temp_df.set_index('timestamp', inplace=True)
        result_df = pd.concat([result_df, temp_df], axis=1)

    result_df = result_df.reset_index()

    result_df['timestamp'] = result_df['timestamp'].astype(str)
    print(result_df)
    # DataFrame을 pickle로 직렬화
    serialized_df = pickle.dumps(result_df)

    # Response 객체에 직렬화된 데이터와 MIME 타입을 지정하여 담기
    response = Response(serialized_df, mimetype='application/octet-stream')

    return response


@app.route('/train', methods=['POST'])
def train():
    input_data = request.get_json()
    data = input_data.get('data')
    df = pd.read_json(data)
    task = input_data.get('task')
    pipeline = input_data.get('pipeline')
    hyperparameters = input_data.get('hyperparameters')
    
    # preprocessing # not implemented

    if task == 'anomaly analysis':
        train_anomaly_analysis(df, pipeline, hyperparameters)
    elif task == 'load prediction':
        train_load_prediction(df, pipeline, hyperparameters)

    return "train complete"

@app.route('/predict', methods=['POST'])
def predict():
    input_data = request.get_json()
    
    
    task = input_data.get('task')
    path = str(input_data.get('path'))

    config = input_data.get('config')
    db_id = get_dbid(config)

    if task == 'anomaly analysis':
        data = input_data.get('data')
        df = pd.read_json(data)
        result_df = predict_anomaly_analysis(server_conn, db_id, df, path)
    elif task == 'load prediction':
        result_df = predict_load_prediction(server_conn, db_id, path, input_data['metric'], input_data['n'])
    
    # DataFrame을 pickle로 직렬화
    serialized_df = pickle.dumps(result_df)

    # Response 객체에 직렬화된 데이터와 MIME 타입을 지정하여 담기
    response = Response(serialized_df, mimetype='application/octet-stream')

    return response

@app.route('/trained_model', methods=['GET'])
def get_trained_models():
    params_json = request.args.get('params')
    args = json.loads(params_json)

    #config = input_data['config']
    task = args['task']
    
    import os
    if task == 'load prediction':
        folder_path = '/root/DBEDA/server/model/trained_model/lp'  # Replace with the path to your folder
    elif task == 'anomaly analysis':
        folder_path = '/root/DBEDA/server/model/trained_model/ade'
    else:
        folder_path = '/root/DBEDA/server/model/trained_model/ad'
    file_names = os.listdir(folder_path)
    file_names = [i for i in file_names if 'ckpt' not in i]

    return jsonify(file_names)


def train_load_prediction(df, pipeline, hyperparameters):
    if pipeline in ['example_pipeline']:
        print("example_pipeline_not_implemented")
    elif pipeline in ['RNN', 'LSTM', 'ARIMA', 'AutoARIMA','TCN', 'Transformer','FFT', 'NBEATS']:
        from model import darts
        darts.lp_train_with_darts(df, pipeline, hyperparameters)

def train_anomaly_analysis(df = None, pipeline = 'anomaly_transformer', hyperparameters = {}):
    if pipeline in ['anomaly_transformer_dbsherlock']: # anoamly detection and explanation
        from model import anomaly_transformer
        anomaly_transformer.ade_train_anomaly_transformer_from_dbsherlock(pipeline, hyperparameters)
        
    elif pipeline in ['kmeans_scorer','pyod','wasserstein']: # anomaly scorer
        from model import darts
        darts.ad_train_with_darts(df, pipeline, hyperparameters)

def predict_anomaly_analysis(server_conn, db_id, df, path):
    # if path.split('.')[-1] == 'pickle':
        #anomaly = orion.detect_with_orion_pipeline(server_conn, db_id, df, path)
    if path.split('_')[0] == 'darts':
        from model import darts
        anomaly = darts.ad_predict_with_darts(server_conn, db_id, df, path)
    elif path.split('_')[0] == 'DBAT':
        from model import anomaly_transformer
        anomaly = anomaly_transformer.ade_predict_anomaly_transformer(server_conn, db_id, df, path)
        

    return anomaly

def predict_load_prediction(server_conn, db_id, path, metric, n):
    # if path.split('.')[-1] == 'pickle':
        #anomaly = orion.detect_with_orion_pipeline(server_conn, db_id, df, path)
    if path.split('_')[0] == 'darts':
        from model import darts
        predicted = darts.lp_predict_with_darts(server_conn, db_id, path, metric, n)
    return predicted


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=server_port, debug=True)
