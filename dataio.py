#
# This program creates a python dictionary containing the data
# in the format needed for main.py
#
# Copyright (C) 2014,  Oscar Dowson
#
import pyodbc
import csv


def connect_to_database(server, database, uid=None, pwd=None):
    if uid is not None:
        connection_string = 'DRIVER={SQL Server}; SERVER=%s;DATABASE=%s;UID=%s;PWD=%s' % (server, database, uid, pwd)
    else:
        connection_string = 'DRIVER={SQL Server}; SERVER=%s;DATABASE=%s' % (server, database)
    
    con = pyodbc.connect(connection_string)
    return con, con.cursor()


def grab_db_categories(cursor, table):
    variables = {'categorical': list(), 'numerical': list()}
    
    for row in cursor.execute("select * from %s" % table):
        if int(row.IsCategorical) == 1:
            variables['categorical'].append(row.Variable)
        else:
            variables['numerical'].append(row.Variable)
    return variables


def build_db_data_dictionary(cursor, table):
    data = dict()
    sql_command = "select * from %s" % table
    cursor.execute(sql_command)
    cols = [column[0] for column in cursor.description]
    for row in cursor.fetchall():
        data[row[0]] = dict(zip(cols, row))
    return data


def get_db_category_levels(cursor, table, variables):
    data = dict()
    for v in variables['categorical']:
        data[v] = list()
        sql_command = "select %s, count(1) from %s group by %s" % (v, table, v)
        for row in cursor.execute(sql_command):
            data[v].append((row[0], float(row[1])))
    return data


def get_db_numerical_metrics(cursor, table, variables):
    data = dict()
    metrics = ['mean', 'var']
    for v in variables['numerical']:
        sql_command = "select avg(%s), var(%s) from %s" % (v, v, table)
        for row in cursor.execute(sql_command):
            data[v] = dict(zip(metrics, row))
    return data


def get_data_from_db(server, database, entity_data_table, variable_classification_table, uid=None, pwd=None):
    con, cursor = connect_to_database(server, database, uid, pwd)
    classification = grab_db_categories(cursor, variable_classification_table)
    entity_data = build_db_data_dictionary(cursor, entity_data_table)
    categorical = get_db_category_levels(cursor, entity_data_table, classification)
    numerical = get_db_numerical_metrics(cursor, entity_data_table, classification)
    db_data = dict()
    db_data['entity_data'] = entity_data
    db_data['categorical_data'] = categorical
    db_data['numerical_data'] = numerical
    return db_data


def grab_ff_categories(filename):
    variables = {'categorical': list(), 'numerical': list()}
    with open(filename, 'r') as f:
        f.readline()
        while True:
            line = f.readline()
            if not line:
                break
            line = line.strip()
            items = csv.reader([line], delimiter='\t').next()
            if int(items[1]) == 1:
                variables['categorical'].append(items[0])
            else:
                variables['numerical'].append(items[0])
    return variables


def split_next_line(f):
    line = f.readline()
    if not line:
        return None
    line = line.strip()
    return csv.reader([line], delimiter='\t').next()


def build_ff_data_dictionary(filename, classification):
    data = dict()
    with open(filename, 'r') as f:
        headers = split_next_line(f)
        while True:
            items = split_next_line(f)
            if items is None:
                break
            data[items[0]] = dict(zip(headers, items))
    for v in classification['numerical']:
        for i in data:
            data[i][v] = float(data[i][v])
    return data


def get_ff_category_levels(data, variables):
    cat = dict()
    for c in variables['categorical']:
        cat[c] = dict()
    for i in data:
        for c in cat:
            if data[i][c] in cat[c]:
                cat[c][data[i][c]] += 1
            else:
                cat[c][data[i][c]] = 1
    categorical = dict()
    for c in cat:
        categorical[c] = list()
        for l in cat[c]:
            categorical[c].append((l, cat[c][l]))
    return categorical


def get_ff_numerical_metrics(data, variables):
    numerical = dict()
    for v in variables['numerical']:
        numerical[v] = {'mean': sum([data[i][v] for i in data]) / len(data)}
        numerical[v]['var'] = sum([pow(data[i][v] - numerical[v]['mean'], 2) for i in data]) / len(data)
    return numerical


def get_data_from_flatfiles(classification_filepath, entity_filepath):
    classification = grab_ff_categories(classification_filepath)
    entity_data = build_ff_data_dictionary(entity_filepath, classification)
    categorical = get_ff_category_levels(entity_data, classification)
    numerical = get_ff_numerical_metrics(entity_data, classification)
    ff_data = dict()
    ff_data['entity_data'] = entity_data
    ff_data['categorical_data'] = categorical
    ff_data['numerical_data'] = numerical
    return ff_data
