import json
import time
import os
import ast
import requests
import random
import boto3
import litmos
import oktaGroups

from litmos import Litmos
from ringcentral import SDK
from botocore.exceptions import ClientError

CHARSET = "UTF-8"
onboarding_pipeline_departments = [
    'General & Administrative'
    'Finance',
    'Legal',
    'Office of CEO',
    'People Ops',
    'Sales & Marketing',
    'Channel Unit',
    'Client Success',
    'Direct to Employer Sales',
    'Sales Ops & Analytics',
    'Implementation',
    'Marketing',
    'Sales'
]
AWS_REGION = os.environ['AWS_REGION']

def lambda_handler(event, context):
    body = event['body']
    secretsValues = get_secret()
    litmos_api = secretsValues['litmos_api']
    jsonBody = json.loads(body)
    jobName = jsonBody['payload']['application']['job']['name']
    application = jsonBody['payload']['application']
    candidate = application['candidate']
    firstName = candidate['first_name']
    lastName = candidate['last_name']
    removeInvalidTextFromName = lastName.split(",", 1)
    lastName = removeInvalidTextFromName[0]
    lastName = "-".join( lastName.split() )
    shipping_address = candidate['custom_fields']['laptop_mailing_address']['value']
    firstLower = firstName.lower()
    lastLower = lastName.lower()
    all_department_items = application['job']['departments']
    rc_clientID = secretsValues['rc_clientID']
    rc_clientSecret = secretsValues['rc_clientSecret']
    rc_accountNumber = secretsValues['rc_accountNumber']
    rc_extensionNumber = secretsValues['rc_extensionNumber']
    rc_accountPassword = secretsValues['rc_accountPassword']
    rc_ServerUrl = secretsValues['rc_ServerUrl']

    for i in all_department_items:
        for k, v in i.items():
            if k == 'name':
                department = v

    respondToGreenhouse()
    # This is to automatically email Lee when a Commercial employee is marked as hired, in order to start the paperwork
    if department in onboarding_pipeline_departments:
        name = f"{firstName} {lastName}"
        SENDER = "it-help@ginger.io"
        RECIPIENT = "onboardingpipeline@ginger.io"
        SUBJECT = "Commercial Team Pre-onboarding Heads-up"   
        BODY_HTML = f"""<html>
        <head></head>
        <body>
            <p>Hi there!</p>
            <p>{name} is coming through the onboarding pipeline and will be setup by IT within 2 weeks.</p>
            <ul>
                <li>New hire: {name}</li>
                <li>Applied to this role: {jobName}</li>
                <li>Department: {department}</li>
            </ul>
            <p>Please check with IT for their startdate, Ginger email, and to confirm the above information is correct.</p>
            <p>All the best!</p>
        </body>
        </html>
                    """
        sendEmail(SENDER, RECIPIENT, SUBJECT, BODY_HTML)

    if (jobName == "Therapist (Full-Time)"):
        print(f"JOB ROLE: Therapist (Full-Time) - {firstName} {lastName}")
        rcDepartment = "Therapist"
        email = f"{firstLower}.{lastLower}@care.ginger.io"
        try:
            gingerEmail = createClinicalOkta(event, rcDepartment, email, secretsValues, rc_clientID, rc_clientSecret, rc_accountNumber, rc_extensionNumber, rc_accountPassword, rc_ServerUrl)
            time.sleep(15)
            while True:
                try:
                    litmosTeam(litmos_api, gingerEmail)
                except Exception as e:
                    print(f"ERROR assigning Litmos team: {e}")
                    litmosTeam(litmos_api, gingerEmail)
                else:
                    print(f"{gingerEmail} was assigned a Litmos Team")
                    break
            emailIT(shipping_address, firstName, lastName)
        except Exception as e:
            print(f"ERROR FOUND: {e}")
            SENDER = "tangerine_distro@ginger.io"
            RECIPIENT = "it-help@ginger.io"
            SUBJECT = "There was an error in Tangerine"
            BODY_HTML = f"""<html>
            <head></head>
            <body>
                <p>{e}</p>
                <p>All the best!</p>
            </body>
            </html>
            """
            sendEmail(SENDER, RECIPIENT, SUBJECT, BODY_HTML)
    else:
        print(f"The role, {jobName}, isn't eligible for Tangerine Automation.")
        return {
            "statusCode": 200
        }

    return {
        "statusCode": 200
    }

def respondToGreenhouse():
    return {
        "statusCode": 200
    }

def get_secret():

    secret_name = "TangerineOnboarding"
    region_name = AWS_REGION

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    # In this sample we only handle the specific exceptions for the 'GetSecretValue' API.
    # See https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
    # We rethrow the exception by default.

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'DecryptionFailureException':
            # Secrets Manager can't decrypt the protected secret text using the provided KMS key.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InternalServiceErrorException':
            # An error occurred on the server side.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            # You provided an invalid value for a parameter.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            # You provided a parameter value that is not valid for the current state of the resource.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'ResourceNotFoundException':
            # We can't find the resource that you asked for.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
    else:
        # Decrypts secret using the associated KMS CMK.
        # Depending on whether the secret is a string or binary, one of these fields will be populated.
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
        else:
            secret = base64.b64decode(get_secret_value_response['SecretBinary'])
    return json.loads(secret)

    
def createClinicalOkta(event, rcDepartment, email, secretsValues, rc_clientID, rc_clientSecret, rc_accountNumber, rc_extensionNumber, rc_accountPassword, rc_ServerUrl):
    body = event['body']
    jsonBody = json.loads(body)
    url = secretsValues['url']
    headersToken = secretsValues['headersToken']
    firstName = jsonBody['payload']['application']['candidate']['first_name']
    lastName = jsonBody['payload']['application']['candidate']['last_name']
    removeInvalidTextFromName = lastName.split(",", 1)
    lastName = removeInvalidTextFromName[0]
    lastName = "-".join( lastName.split() )
    firstLower = firstName.lower()
    lastLower = lastName.lower()

    try:
        print(f"Checking if {email} exists")
        gingerEmail = checkIfUserExists(email, url, headersToken, firstLower, lastLower)
        ringCentral(firstName, lastName, gingerEmail, rcDepartment, rc_clientID, rc_clientSecret, rc_accountNumber, rc_extensionNumber, rc_accountPassword, rc_ServerUrl)
        createOktaUser(url, headersToken, jsonBody, gingerEmail)
    except Exception as e:
        print(f"ERROR FOUND: {e}")
        SENDER = "tangerine_distro@ginger.io"
        RECIPIENT = "it-help@ginger.io"
        SUBJECT = "There was an error in Tangerine"
        BODY_HTML = f"""<html>
        <head></head>
        <body>
            <p>{e}</p>
            <p>All the best!</p>
        </body>
        </html>
        """
        sendEmail(SENDER, RECIPIENT, SUBJECT, BODY_HTML)

    return gingerEmail

def checkIfUserExists(email, url, headersToken, firstLower, lastLower):
    headers = {
        "accept": "application/json",
        "authorization" : headersToken,
        "content-type": "application/json"
    }

    email.replace('@', '%40')
    response = requests.get(f"https://{url}/api/v1/users/{email}", headers=headers)
    responseJson = json.loads(response.text)

    if responseJson['errorCode'] == 'E0000007':
        print('This is a new employee')
        gingerEmail = email
        return gingerEmail
    elif responseJson['status'] == 'STAGED':
        print('This user is staged in Okta, closing now.')
        SENDER = "tangerine_distro@ginger.io@ginger.io"
        RECIPIENT = "it-help@ginger.io"
        SUBJECT = "Duplicate user pushed through Tangerine"
        BODY_HTML = f"""<html>
            <head></head>
            <body>
                <p>Hi IT,</p>
                <p>{email} was attempted to be pushed through Tangerine, however this email is in use and is staged in Okta.</p>
                <p>This may be the same person or a second employee of the same name, please check with Recruiting to find out if they need to be manually provisioned.</p>
                <p>All the best!<p>
            </body>
            </html>
            """
        sendEmail(SENDER, RECIPIENT, SUBJECT, BODY_HTML)
        return {
            "statusCode": 200
        }
    elif responseJson['status'] == 'ACTIVE':
        if "care.ginger.io" in email:
            print('A care email of this name is already in use')
            gingerEmail = f"{lastLower}.{firstLower}@care.ginger.io"
            print(gingerEmail)
        else:
            print('An INC email of this name is already in use')
            gingerEmail = f"{firstLower[:2]}{lastLower}@ginger.io"
            print(gingerEmail)
    else:
        gingerEmail = email

    return gingerEmail

def createOktaUser(url, headersToken, jsonBody, gingerEmail):
    application = jsonBody['payload']['application']
    candidate = application['candidate']
    firstName = candidate['first_name']
    lastName = candidate['last_name']
    removeInvalidTextFromName = lastName.split(",", 1)
    lastName = removeInvalidTextFromName[0]
    lastName = "-".join( lastName.split() )
    jobName = application['job']['name']
    emailList = candidate['email_addresses']
    personalEmail = emailList[0]['value']
    

    if jobName == "Therapist (Full-Time)":
        data = {
            "profile": {
                "firstName": firstName,
                "lastName": lastName,
                "email": gingerEmail,
                "secondEmail": personalEmail,
                "login": gingerEmail,
                "department": "clinical-care"
            },
            "groupIds": oktaGroups.therapistPartTime
        }
        setOktaGroups(url, headersToken, data)

def setOktaGroups(url, headersToken, data):
    headers = {
        "accept": "application/json",
        "authorization" : headersToken,
        "content-type": "application/json"
    }

    print('CREATING USER IN OKTA')
    response = requests.post(f"https://{url}/api/v1/users?activate=false", headers=headers, json=data)
    return response.text


def litmosTeam(litmos_api, gingerEmail):
    litmos = Litmos(litmos_api, 'gingerio.litmos.com', 'https://api.litmos.com/v1.svc')

    user = litmos.User.find(gingerEmail)
    all_teams = litmos.Team.all()
    for team in all_teams:
        if team.Name == 'Therapists and Psychologists':
            team.add_users([user])


def ringCentral(firstName, lastName, gingerEmail, rcDepartment, rc_clientID, rc_clientSecret, rc_accountNumber, rc_extensionNumber, rc_accountPassword, rc_ServerUrl):
    queryParams = {
        'page': 1,
        'perPage': 100,
        'status': [ 'Unassigned' ]
    }
    #clientID, clientSecret, serverURL
    rcsdk = SDK(rc_clientID, rc_clientSecret, rc_ServerUrl)
    platform = rcsdk.platform()
    # This *has* to be tied to the user account of extension 101. This is Puneet's account, should he leave Ginger and his RC account is deleted, this is why this will break. The password for this account is in Secrets Manager and also in the shared-corp-apps LastPass folder.
    #phonenumber, extensionnumber, password
    platform.login(rc_accountNumber, rc_extensionNumber, rc_accountPassword)

    extensions = platform.get(f'/restapi/v1.0/account/~/extension', queryParams)

    recordCount = 0
    for record in extensions.json().records:
        # Only assign the first extension that is returned but coninue the count to make sure we have enough extensions in stock
        if recordCount == 0:
            extensionId = record.id
        recordCount += 1
    if extensionId:
        updateExtension = {
            'contact': {
                'firstName': firstName,
                'lastName': lastName,
                'company': 'Ginger.io',
                'email': gingerEmail,
                'emailAsLoginName': 'True',
                'department': rcDepartment
            },
            'hidden': 'True',
            'regionalSettings': {
                'timeFormat': '12h'
            },
            'status': 'Enabled',
            'type': 'User'
        }

        platform.put(f'/restapi/v1.0/account/~/extension/{extensionId}', updateExtension)

        if recordCount <= 15:
            recordCount = 0
            SENDER = "tangerine_distro@ginger.io"
            RECIPIENT = "it-help@ginger.io"
            SUBJECT = "RingCentral Extension Stock is Low!"
                    
            BODY_HTML = """<html>
                <head></head>
                <body>
                    <p>Hi IT,</p>
                    <p>The RingCentral Extension supply is running low!</p>
                    <p>Please purchase more (15-30) as soon as possible.</p>
                    <p>All the best!</p>
                </body>
                </html>
                            """  
            sendEmail(SENDER, RECIPIENT, SUBJECT, BODY_HTML)
        
    # ExtensionID is null - no extensions available
    else:
        SENDER = "tangerine_distro@ginger.io"
        RECIPIENT = "it-help@ginger.io"
        SUBJECT = "There was an issue assigning a RingCentral number"
                
        BODY_HTML = f"""<html>
            <head></head>
            <body>
                <p>Hi IT,</p>
                <p>There was an issue assigning a RingCentral number to {gingerEmail} through Tangerine Onboarding.</p>
                <p>This is most likel because there are no available extensions. Please investigate this and remediate ASAP.</p>
                <p>All the best!</p>
            </body>
            </html>
                        """
        sendEmail(SENDER, RECIPIENT, SUBJECT, BODY_HTML)

def emailIT(shipping_address, firstName, lastName):
    if shipping_address:
        name = f"{firstName} {lastName}"
        SENDER = "tangerine_distro@ginger.io"
        RECIPIENT = "it-help@ginger.io"

        SUBJECT = f"New Employee Onboarded through Tangerine - {name}"
        BODY_HTML = f"""<html>
        <head></head>
        <body>
            <p>Hi IT,</p>
            <p>{name} has just been marked as Hired on Greenhouse, they should be pushed by PeopleOps through UKG soon.</p>
            <p>Here's their shipping address for their Ginger laptop:</p>
            <p>{shipping_address}</p>
            <p>All the best!<p>
        </body>
        </html>
                    """
        sendEmail(SENDER, RECIPIENT, SUBJECT, BODY_HTML)
    else:
        name = f"{firstName} {lastName}"
        SENDER = "tangerine_distro@ginger.io"
        RECIPIENT = "it-help@ginger.io"

        SUBJECT = f"New Employee Onboarded through Tangerine - {name}"
        BODY_HTML = f"""<html>
        <head></head>
        <body>
            <p>Hi IT,</p>
            <p>{name} has just been marked as Hired on Greenhouse, they should be pushed by PeopleOps through UKG soon.</p>
            <p>There was no shipping address included, please contact PeopleOps for this information once launched.</p>
            <p>All the best!<p>
        </body>
        </html>
                    """
        sendEmail(SENDER, RECIPIENT, SUBJECT, BODY_HTML)

def sendEmail(SENDER, RECIPIENT, SUBJECT, BODY_HTML): 
    # AWS_REGION = "us-west-2"
    client = boto3.client('ses',region_name=AWS_REGION)
    response = client.send_email(
        Destination={
            'ToAddresses': [
                RECIPIENT,
            ],
        },
        Message={
            'Body': {
                'Html': {
                    'Charset': CHARSET,
                    'Data': BODY_HTML,
                },
            },
            'Subject': {
                'Charset': CHARSET,
                'Data': SUBJECT,
            },
        },
        Source=SENDER,
    )
    print(f"{SUBJECT} email sent! Message ID: {response['MessageId']}")