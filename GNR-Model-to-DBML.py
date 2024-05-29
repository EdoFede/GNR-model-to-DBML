import sys
import os
import re
from collections import OrderedDict

projectDir = sys.argv[1]

indent = '    '

SysFieldsDefault = {
    'id': True,
    'ins': True,
    'upd': True,
    'ldel': True,
    'user_ins': False,
    'user_upd': False,
    'draftField': False,
    'counter': None,
    'hierarchical': None,
    'df': False
}

dTypeTrans = {
    'T': 'Text',
    'N': 'Numeric',
    'I': 'Integer',
    'L': 'Long',
    'B': 'Bool',
    'D': 'Date',
    'H': 'Time',
    'DH': 'DateTime',
    'P': 'Image',
    'X': 'Bag'
}

def extractTextFromBrackets(string):
    stack = 0
    startIndex = None

    for i, c in enumerate(string):
        if c == '(':
            if stack == 0:
                startIndex = i + 1
            stack += 1
        elif c == ')':
            stack -= 1
            if stack == 0:
                return string[startIndex:i].strip()
    return

def compactDefinition(string):
    pattern = r'\s*,\s*'
    return re.sub(pattern, ',', string)

def stringToDict(string):
    resDict = {}

    params = string.split(',')
    for param in params:
        if param.count('=') != 1:
            continue
        (k, v) = param.split('=')
        resDict[k] = v.replace("'", "").replace("\"", "")
    return resDict

def tableFileRead(fileName):
    tableDict = {}
    columns = []
    relations = []

    # Read the content of the file
    content = ""
    with open(fileName, 'r') as file:
        lines = file.readlines()
        filteredLines = [line for line in lines if not line.lstrip().startswith('#')]
        content = ''.join(filteredLines)


    # Extract table info
    tabMatches = re.finditer("pkg\\.table\\(", content)
    for match in tabMatches:
        start_index = match.start()
        end_index = match.end()

        defin = 'name=' + compactDefinition(extractTextFromBrackets(content[start_index:]))
        tableDict = stringToDict(defin)


    # Extract sysFields
    sysFieldsMathes = re.finditer("\\.sysFields\\(", content)
    for match in sysFieldsMathes:
        start_index = match.start()
        end_index = match.end()

        defin = 'instance=' + compactDefinition(extractTextFromBrackets(content[start_index:]))
        tableDict['sysFields'] = stringToDict(defin)


    # Add ID column from sysFields
    if 'sysFields' in tableDict:
        sysFields = SysFieldsDefault.copy()

        for k,v in sysFields.items():
            if k in tableDict['sysFields']:
                sysFields[k] = tableDict['sysFields'][k]

        if sysFields['id'] == True:
            IDcolumn = {'name': 'id', 'size': '22', 'unique': 'True', 'validate_notnull': 'True'}
            columns.append(IDcolumn)


    # Extract columns
    colMatches = re.finditer(".+.(alias|formula|py|)[cC]olumn\\(", content)
    for match in colMatches:
        start_index = match.start()
        end_index = match.end()

        paramsDict = {}

        # Extract column type (column, aliasColoumn, ...)    
        cType = content[(start_index):(end_index-1)].lstrip()
        cType = re.search('(alias|formula|py|)[cC]olumn', cType).group()
        paramsDict['cType'] = cType

        # Extract column parameters
        defin = 'name=' + compactDefinition(extractTextFromBrackets(content[start_index:]))
        paramsDict = stringToDict(defin)

        # Add column dictionary to the column list
        columns.append(paramsDict)

    tableDict['columns'] = columns


    # Extract relations
    relMatches = re.finditer("\\)\\.relation\\(", content)
    for match in relMatches:
        start_index = match.start()
        end_index = match.end()

        # Extract relations parameters
        defin = 'destination=' + compactDefinition(extractTextFromBrackets(content[(end_index-1):]))
        relDict = stringToDict(defin)

        # Extract source column
        sourceMatches = list(re.finditer('.(alias|formula|py|)[cC]olumn\\(', content[:start_index]))
        if sourceMatches:
            lastMatch = sourceMatches[-1]
            sourceColIdx = lastMatch.start()
        sourceCol = 'source=' + compactDefinition(extractTextFromBrackets(content[sourceColIdx:]))
        relDict['source'] = tableDict['name'] + '.' + stringToDict(sourceCol)['source']

        relations.append(relDict)

    tableDict['relations'] = relations

    return tableDict

def translateTypes(string):
    dType = string
    if not dType:
        dType = 'T'

    try:
        dType = dTypeTrans[dType]
    except:
        pass
    return dType

def generateDBML(tables):
    dbDiagramTxt = ""
    for table in tables:
        dbDiagramTxt += 'Table ' + table['name'] + '{\n'

        for column in table['columns']:
            dType = 'T'
            try:
                dType = column['dtype']
            except: 
                pass

            dbDiagramTxt += indent + column['name'] + ' ' 
            dbDiagramTxt += translateTypes(dType)
            try:
                dbDiagramTxt += '(' + column['size'].replace(':', '') + ')'
            except: 
                pass

            dbDiagramTxt += ' ['
            try:
                if column['name'] == table['pkey']:
                    dbDiagramTxt += 'pk,'
            except: 
                pass

            try:
                if column['unique'] == 'True':
                    dbDiagramTxt += 'unique,'
            except: 
                pass

            try:
                if column['validate_notnull'] == 'True':
                    dbDiagramTxt += 'not null,'
            except: 
                pass

            try:
                dbDiagramTxt += 'default: ' + column['default'] + ','
            except: 
                pass

            try:
                dbDiagramTxt += 'note: \'' + column['name_long'] + '\','
            except: 
                pass

            dbDiagramTxt = dbDiagramTxt.rstrip(',') + ']'

            dbDiagramTxt += '\n'

        if 'name_long' in table:
            dbDiagramTxt += '\n' + indent + 'Note: \'' + table.get('name_long') + '\'\n'

        dbDiagramTxt += '}\n\n'

        for relation in table['relations']:
            dbDiagramTxt += 'Ref' 
            # dbDiagramTxt += ' ' + relation['relation_name']
            dbDiagramTxt += ': '
            dbDiagramTxt += relation['source']
            if 'one_one' in relation:
                dbDiagramTxt += ' - '
            else:
                dbDiagramTxt += ' > '
            dbDiagramTxt += relation['destination']
            # dbDiagramTxt += ' [delete: cascade, update: no action]'   // TBD
            dbDiagramTxt += '\n'
        dbDiagramTxt += '\n'
    return dbDiagramTxt

def main():
    tables = []

    modelPath = os.path.join(projectDir, 'model')
    files = os.listdir(modelPath)
    modelFiles = [f for f in files if f.endswith('.py')]

    for modelFile in modelFiles:
        fileName = os.path.join(modelPath, modelFile)
        tables.append(tableFileRead(fileName))

    print(generateDBML(tables))

if __name__ == '__main__':
    main()
