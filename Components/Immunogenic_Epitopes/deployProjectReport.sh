# This script will install dependencies, bundle the lambda function, and deploy to the AWS lambda environment.
# Y must have the AWS commandline environment already installed
# And you must have previously run "aws configure" to set up your machine for access to the AWS Environment.
# You need to provide the config file validation_config.yml with entries url: {} username: {} password: {}
# Feel free to try it without activating the virtual environment (remove the line source $ENVIRONMENT_PATH"/bin/activate")
# it may or may not be necessary depending on your local python environment.
PROJECT_PATH="/home/bmatern/github/Converters/Components/Immunogenic_Epitopes"
ENVIRONMENT_PATH="/home/bmatern/github/Converters/venv"
HANDLER_FILE="ImmunogenicEpitopesProjectReport.py"
#LAMBDA_FUNCTION="validateImmunogenicEpitopesStaging"
LAMBDA_FUNCTION="projectReportImmunogenicEpitopesProd"

cd $PROJECT_PATH

# In case an old zip file is still here.
rm function.zip

# Install package(s)
source $ENVIRONMENT_PATH"/bin/activate"
pip install --target ./package xlrd
pip install --target ./package pyyaml
pip install --target ./package xlsxwriter
pip install --target ./package zipfile
pip install --target ./package git+https://github.com/nmdp-bioinformatics/pyglstring
deactivate

# Zip packages
cd package
zip -r9 $PROJECT_PATH"/function.zip" .

# Zip Script
cd ..
zip -g function.zip $HANDLER_FILE

# Zip supporting files. -j flag will junk the relative paths.
zip -j -g function.zip ImmunogenicEpitopesValidator.py
zip -j -g function.zip ../../Common/Validation.py
zip -j -g function.zip ../../Common/ParseExcel.py
zip -j -g function.zip ../../Common/ParseXml.py
zip -j -g function.zip ../../Common/IhiwRestAccess.py
zip -j -g function.zip ../../Common/S3_Access.py

# Zip Config File
zip -g function.zip validation_config.yml

# Upload to AWS
aws lambda update-function-code --function-name $LAMBDA_FUNCTION --zip-file fileb://function.zip
