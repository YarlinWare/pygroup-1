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
    data = list()
    sql_command = "select * from %s" % table
    cursor.execute(sql_command)
    cols = [column[0] for column in cursor.description]
    for row in cursor.fetchall():
        data.append(dict(zip(cols,row)))
    return(data)

server = '.'
database = 'enggen403'

con, cursor = connectToDatabase(server, database)

variables = grabCategories(cursor, 'categories')
data = buildDataDictionary(cursor, 'class_data')
