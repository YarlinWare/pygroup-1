import pyodbc

def connectToDatabase(server, database, uid=None, pwd=None):
    if uid is not None:
        connection_string = 'DRIVER={SQL Server}; SERVER=%s;DATABASE=%s;UID=%s;PWD=%s' % (server, database, uid, pwd)
    else:
        connection_string = 'DRIVER={SQL Server}; SERVER=%s;DATABASE=%s' % (server, database)
    
    con = pyodbc.connect(connection_string)
    return con, con.cursor()

def grabCategories(cursor, table):
    variables = {'categorical': list(), 'numerical': list()}
    
    for row in cursor.execute("select * from %s" % table):
        if int(row.IsCategorical)==1:
            variables['categorical'].append(row.Variable)
        else:
            variables['numerical'].append(row.Variable)
    return variables

def buildDataDictionary(cursor, table):
    data = dict()
    sql_command = "select * from %s" % table
    cursor.execute(sql_command)
    cols = [column[0] for column in cursor.description]
    for row in cursor.fetchall():
        data[row[0]] = dict(zip(cols,row))
    return(data)

def getCategoryLevels(cursor, table, variables):
    data = dict()
    for v in variables['categorical']:
        data[v] = list()
        sql_command = "select %s, count(1) from %s group by %s" % (v, table, v)
        for row in cursor.execute(sql_command):
            data[v].append((row[0], float(row[1])))
    return(data)

def getNumericalMetrics(cursor, table, variables):
    data = dict()
    metrics = ['mean', 'var']
    for v in variables['numerical']:
        sql_command = "select avg(%s), var(%s) from %s" % (v, v, table)
        for row in cursor.execute(sql_command):
            data[v] = dict(zip(metrics, row))
    return(data)
