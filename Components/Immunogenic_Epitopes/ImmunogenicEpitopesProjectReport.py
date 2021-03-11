from boto3 import client
#import json
#import urllib
from Common.ParseExcel import createExcelTransplantationReport

try:
    import IhiwRestAccess
    import ParseExcel
    import ParseXml
    import Validation
    import S3_Access
    import ImmunogenicEpitopesValidator
except Exception as e:
    print('Failed in importing files: ' + str(e))
    from Common import IhiwRestAccess
    from Common import ParseExcel
    from Common import ParseXml
    from Common import Validation
    from Common import S3_Access
    import ImmunogenicEpitopesValidator

s3 = client('s3')
from sys import exc_info

import zipfile
import io
from time import sleep

def immunogenic_epitope_project_report_handler(event, context):
    print('Lambda handler: Creating a project report for immunogenic epitopes.')
    # This is the AWS Lambda handler function.
    try:
        # Sleep 1 second, enough time to make sure the file is available.
        sleep(1)
        # TODO: get the bucket from the sns message ( there is no sns message, trigger one?)
        #bucket = content['Records'][0]['s3']['bucket']['name']
        bucket = 'ihiw-management-upload-prod'
        #bucket = 'ihiw-management-upload-staging'

        #adminUserID=

        createImmunogenicEpitopesReport(bucket=bucket)

    except Exception as e:
        print('Exception:\n' + str(e) + '\n' + str(exc_info()))
        return str(e)


def createUploadEntriesForReport(summaryFileName=None, zipFileName=None):
    # TODO: This should be a standalone upload, not a child upload. Need some work on this part.

    # TODO: This will also make multiple copies. I should check if the report file already exists and/or (probably) overwrite it
    parentUploadName = '1497_1615205312528_PROJECT_DATA_MATRIX_ProjectReport'
    url = IhiwRestAccess.getUrl()
    token = IhiwRestAccess.getToken(url=url)

    if(url is not None and token is not None and len(url)>0 and len(token)>0):

        IhiwRestAccess.createConvertedUploadObject(newUploadFileName=summaryFileName
                                                   , newUploadFileType='OTHER'
                                                   , previousUploadFileName=parentUploadName
                                                   , url=url, token=token)
        IhiwRestAccess.createConvertedUploadObject(newUploadFileName=zipFileName
                                                   , newUploadFileType='OTHER'
                                                   , previousUploadFileName=parentUploadName
                                                   , url=url, token=token)

        IhiwRestAccess.setValidationStatus(uploadFileName=parentUploadName, isValid=True,
                                           validationFeedback='Valid Report.', validatorType='PROJECT_REPORT', url=url,
                                           token=token)
        IhiwRestAccess.setValidationStatus(uploadFileName=summaryFileName, isValid=True,
                                           validationFeedback='Valid Report.', validatorType='PROJECT_REPORT', url=url,
                                           token=token)
        IhiwRestAccess.setValidationStatus(uploadFileName=zipFileName, isValid=True,
                                           validationFeedback='Valid Report.', validatorType='PROJECT_REPORT', url=url,
                                           token=token)
    else:
        raise Exception('Could not create login token when creating upload entries for report files.')

def getTransplantationReportSpreadsheet(donorTyping=None, recipientTyping=None, recipHamlPreTxFilename=None, recipHamlPostTxFilename=None, s3=None, bucket=None):
    recipPreTxAntibodyData = ParseXml.parseHamlFileForBeadData(hamlFileName=recipHamlPreTxFilename, s3=s3, bucket=bucket)
    recipPostTxAntibodyData = ParseXml.parseHamlFileForBeadData(hamlFileName=recipHamlPostTxFilename, s3=s3, bucket=bucket)
    transplantationReportSpreadsheet = ParseExcel.createExcelTransplantationReport(donorTyping=donorTyping, recipientTyping=recipientTyping, recipPreTxAntibodyData=recipPreTxAntibodyData, recipPostTxAntibodyData=recipPostTxAntibodyData, preTxFileName=recipHamlPreTxFilename, postTxFileName=recipHamlPostTxFilename)
    return transplantationReportSpreadsheet

def createImmunogenicEpitopesReport(bucket=None):
    print('Creating an Immunogenic Epitopes Submission Report.')

    url=IhiwRestAccess.getUrl()
    token=IhiwRestAccess.getToken(url=url)
    immuEpsProjectID = IhiwRestAccess.getProjectID(projectName='immunogenic_epitopes')
    dqEpsProjectID = IhiwRestAccess.getProjectID(projectName='dq_immunogenicity')
    #summaryFileName = 'Project.' + str(immuEpsProjectID) + '.Report.xlsx'
    #zipFileName = 'Project.' + str(immuEpsProjectID) + '.Report.zip'
    summaryFileName = 'ImmunogenicEpitopes.ProjectReport.xlsx'
    zipFileName = 'ImmunogenicEpitopes.ProjectReport.zip'



    dataMatrixUploadList = getDataMatrixUploads(projectIDs=[immuEpsProjectID, dqEpsProjectID], token=token, url=url)

    # Create Spreadsheet, Define Headers?
    outputWorkbook, outputWorkbookbyteStream = ParseExcel.createBytestreamExcelOutputFile()
    outputWorksheet = outputWorkbook.add_worksheet()
    # Define Styles
    headerStyle = outputWorkbook.add_format({'bold': True})
    errorStyle = outputWorkbook.add_format({'bg_color': 'red'})
    # Write headers on new sheet.
    summaryHeaders = ['data_matrix_filename','submitting_user','submitting_lab','submission_date', 'donor_glstring', 'recipient_glstring']
    dataMatrixHeaders=ImmunogenicEpitopesValidator.getColumnNames(isImmunogenic=True)

    #print('These are the summary headers:' + str(summaryHeaders))
    #print('These are the data matrix headers:' + str(dataMatrixHeaders))

    for headerIndex, header in enumerate(summaryHeaders):
        cellIndex = ParseExcel.getColumnNumberAsString(base0ColumnNumber=headerIndex) + '1'
        outputWorksheet.write(cellIndex, header, headerStyle)

    for headerIndex, header in enumerate(dataMatrixHeaders):
        cellIndex = ParseExcel.getColumnNumberAsString(base0ColumnNumber=headerIndex+len(summaryHeaders)) + '1'
        outputWorksheet.write(cellIndex, header, headerStyle)

    reportLineIndex = 1

    supportingUploadFilenames = []
    # These are reports. Key=filename, value=(String) with file contents.
    transplantationReportFiles={}
    #supportingFiles = ['1497_1593502560693_HML_HmlRecipient.xml'] # Test data.

    # preload an upload list to use repeatedly later
    allUploads = IhiwRestAccess.getUploads(token=token,url=url)

    # Combine data matrices together.
    for dataMatrixUpload in dataMatrixUploadList:
        #print('Checking Validation of this file:' + dataMatrixUpload['fileName'])
        #print('This is the upload: ' + str(dataMatrixUpload))

        excelFileObject = s3.get_object(Bucket=bucket, Key=dataMatrixUpload['fileName'])

        inputExcelBytes = excelFileObject["Body"].read()
        # validateEpitopesDataMatrix returns all the information we need.
        (validationResults, inputExcelFileData, errorResultsPerRow) = ImmunogenicEpitopesValidator.validateEpitopesDataMatrix(excelFile=inputExcelBytes, isImmunogenic=True, projectIDs=[immuEpsProjectID, dqEpsProjectID])
        #print('This file has this validation status:' + validationResults)

        if(inputExcelFileData is not None):
            supportingUploadFilenames.append(dataMatrixUpload['fileName'])
            dataMatrixFileName = dataMatrixUpload['fileName']
            submittingUser = dataMatrixUpload['createdBy']['user']['firstName'] + ' ' + dataMatrixUpload['createdBy']['user']['lastName'] + ':\n' + dataMatrixUpload['createdBy']['user']['email']
            submittingLab = dataMatrixUpload['createdBy']['lab']['department'] + ', ' + dataMatrixUpload['createdBy']['lab']['institution']
            submissionDate = dataMatrixUpload['createdAt']



            # Loop input Workbook data
            for dataLineIndex, dataLine in enumerate(inputExcelFileData):
            # print('Copying this line:' + str(dataLine))
                reportLineIndex += 1

                outputWorksheet.write(ParseExcel.getColumnNumberAsString(base0ColumnNumber=0) + str(reportLineIndex), dataMatrixFileName)
                outputWorksheet.write(ParseExcel.getColumnNumberAsString(base0ColumnNumber=1) + str(reportLineIndex), submittingUser)
                outputWorksheet.write(ParseExcel.getColumnNumberAsString(base0ColumnNumber=2) + str(reportLineIndex), submittingLab)
                outputWorksheet.write(ParseExcel.getColumnNumberAsString(base0ColumnNumber=3) + str(reportLineIndex), submissionDate)

                donorGlString = '?'
                recipientGlString = '?'
                recipHamlPreTxFileName = '?'
                recipHamlPostTxFileName = '?'


                for headerIndex, header in enumerate(dataMatrixHeaders):
                    cellIndex = ParseExcel.getColumnNumberAsString(base0ColumnNumber=headerIndex+len(summaryHeaders)) + str(reportLineIndex)

                    currentGlString = None
                    # Add supporting files.
                    fileResults=[]
                    if(header.endswith('_hla')):
                        fileResults=IhiwRestAccess.getUploadFileNamesByPartialKeyword(uploadTypeFilter=['HML'], token=token, url=url, fileName=str(dataLine[header]), projectIDs=[immuEpsProjectID, dqEpsProjectID], allUploads=allUploads)

                        if(len(fileResults) == 1):
                            # We found a single file mapped to this HLA result. Get a GlString.
                            currentGlString = ParseXml.getGlStringFromHml(hmlFileName=fileResults[0]['fileName'], s3=s3, bucket=bucket)
                            glStringValidationResults = Validation.validateGlString(glString=currentGlString)
                        else:
                            # We didn't find a single file to calculate a glString from. Use the existing data
                            currentGlString = dataLine[header]
                            glStringValidationResults = errorResultsPerRow[dataLineIndex][header]

                        # print the glString in the appropriate column
                        if(header=='donor_hla'):
                            donorGlString=currentGlString
                            if(len(glStringValidationResults) > 0):
                                outputWorksheet.write(ParseExcel.getColumnNumberAsString(base0ColumnNumber=4) + str(reportLineIndex), currentGlString, errorStyle)
                                outputWorksheet.write_comment(ParseExcel.getColumnNumberAsString(base0ColumnNumber=4) + str(reportLineIndex), glStringValidationResults)
                            else:
                                outputWorksheet.write(ParseExcel.getColumnNumberAsString(base0ColumnNumber=4) + str(reportLineIndex), currentGlString)
                        elif(header=='recipient_hla'):
                            recipientGlString=currentGlString
                            if (len(glStringValidationResults) > 0):
                                outputWorksheet.write(ParseExcel.getColumnNumberAsString(base0ColumnNumber=5) + str(reportLineIndex), currentGlString, errorStyle)
                                outputWorksheet.write_comment(ParseExcel.getColumnNumberAsString(base0ColumnNumber=5) + str(reportLineIndex), glStringValidationResults)
                            else:
                                outputWorksheet.write(ParseExcel.getColumnNumberAsString(base0ColumnNumber=5) + str(reportLineIndex), currentGlString)
                        else:
                            raise Exception ('I cannot understand to do with the data for column ' + str(header) + ':' + str(dataLine[header]))

                    elif('_haml_' in (header)):
                        # TODO: Include Antibody_CSV?
                        fileResults=IhiwRestAccess.getUploadFileNamesByPartialKeyword(uploadTypeFilter=['HAML'], token=token, url=url, fileName=str(dataLine[header]), projectIDs=[immuEpsProjectID, dqEpsProjectID], allUploads=allUploads)
                        #print('I just found these haml results:' + str(fileResults))

                        # TODO: Assuming a single HAML file here. What if !=1 results are found?
                        if(header=='recipient_haml_pre_tx' and len(fileResults)==1):
                            recipHamlPreTxFileName = fileResults[0]['fileName']
                        elif(header=='recipient_haml_post_tx' and len(fileResults)==1):
                            recipHamlPostTxFileName = fileResults[0]['fileName']
                        else:
                            pass

                    else:
                        pass

                    for uploadFile in fileResults:
                        #print('Appending this file to the upload list:' + str(uploadFile))
                        supportingUploadFilenames.append(uploadFile['fileName'])

                    # Was there an error in this cell? Highlight it red and add error message
                    if (header in errorResultsPerRow[dataLineIndex].keys() and len(str(errorResultsPerRow[dataLineIndex][header])) > 0):
                        # TODO: Make the error styles optional.
                        outputWorksheet.write(cellIndex, dataLine[header], errorStyle)
                        outputWorksheet.write_comment(cellIndex, errorResultsPerRow[dataLineIndex][header])
                    else:
                        # TODO: What if a dataline is missing a bit of information? Handle if this is missing in the input file.
                        outputWorksheet.write(cellIndex, dataLine[header])

                # TODO: make these excel files with highlighting.
                transplantationReportFileName = 'AntibodyReport_' + dataMatrixUpload['fileName'] + '_Row' + str(dataLineIndex+2) + '.xlsx'
                transplantationReportText = getTransplantationReportSpreadsheet(donorTyping=donorGlString, recipientTyping=recipientGlString, recipHamlPreTxFilename=recipHamlPreTxFileName, recipHamlPostTxFilename=recipHamlPostTxFileName ,s3=s3, bucket=bucket)
                transplantationReportFiles[transplantationReportFileName]=transplantationReportText
        else:
            print('No workbook data was found for data matrix ' + str(dataMatrixUpload['fileName']) )
            print('Upload ID of missing data matrix:' +  str(dataMatrixUpload['id']) )

    createUploadEntriesForReport(summaryFileName=summaryFileName, zipFileName=zipFileName)

    # Widen the columns a bit so we can read them.
    outputWorksheet.set_column('A:' + ParseExcel.getColumnNumberAsString(len(dataMatrixHeaders) - 1), 30)
    # Freeze the header row.
    outputWorksheet.freeze_panes(1, 0)
    outputWorkbook.close()
    S3_Access.writeFileToS3(newFileName=summaryFileName, bucket=bucket, s3ObjectBytestream=outputWorkbookbyteStream)




    # create zip file
    zipFileStream = io.BytesIO()
    supportingFileZip = zipfile.ZipFile(zipFileStream, 'a', zipfile.ZIP_DEFLATED, False)

    #supportingFileZip.writestr('HelloWorld.txt', 'Hello World!')
    supportingFileZip.writestr(summaryFileName, outputWorkbookbyteStream.getvalue())

    for supportingFile in list(set(supportingUploadFilenames)):
        print('Adding file ' + str(supportingFile) + ' to ' + str(zipFileName))

        supportingFileObject = s3.get_object(Bucket=bucket, Key=supportingFile)
        # TODO: We're writing a string in the zip file.
        #  I think that's fine for hml & text-like files but this might cause problems with some file types.
        supportingFileZip.writestr(supportingFile, supportingFileObject["Body"].read())

    for transplantationReportFileName in transplantationReportFiles:
        supportingFileZip.writestr(transplantationReportFileName, transplantationReportFiles[transplantationReportFileName])

    supportingFileZip.close()
    S3_Access.writeFileToS3(newFileName=zipFileName, bucket=bucket, s3ObjectBytestream=zipFileStream)



    print('Done. Summary is here: ' + str(summaryFileName) + '\nSupporting zip is here: ' + str(zipFileName)
          + '\nin bucket: ' + str(bucket))

def getDataMatrixUploads(projectIDs=None, token=None, url=None):
    # collect all data matrix files.
    uploadList = IhiwRestAccess.getUploads(token=token, url=url)
    #print('I found these uploads:' + str(uploadList))
    #print('This is my upload list:' + str(uploadList))
    print('Parsing ' + str(len(uploadList)) + ' uploads to find data matrices for project(s) ' + str(projectIDs) + '..')
    if(not isinstance(projectIDs, list)):
        projectIDs = [projectIDs]
    dataMatrixUploadList = []
    for upload in uploadList:
        if (upload['project']['id'] in projectIDs):
            if (upload['type'] == 'PROJECT_DATA_MATRIX'):
                dataMatrixUploadList.append(upload)
            else:
                # print('Disregarding this upload because it is not a data matrix.')
                pass
        else:
            # print('Disregarding this upload because it is not in our project.')
            pass
    print(
        'I found a total of ' + str(len(dataMatrixUploadList)) + ' data matrices for project' + str(projectIDs) + '.\n')
    return dataMatrixUploadList







