# ----------------------------------------------------------------------------------
# crossAccountMaster is a Lambda 'parent' function that invokes child functions against other AWS accounts,
# using cross-account credentials.  Credentials are passed to the child functions
# as event data (cross-account ARN, event ID and customer name).
# ----------------------------------------------------------------------------------

import boto3
import json

client = boto3.client('lambda')
ssm_client = boto3.client('ssm')

def lambda_handler(event, context):

    # ----------------------------------------------------------------------------------
    # Get the list of ARNs of cross-account IAM roles saved in SSM Parameter crossAccountRoleARNList
    # ----------------------------------------------------------------------------------
    rolearnlist = []
    rolearnlist_from_ssm = ssm_client.get_parameter(Name='crossAccountRoleARNList')
    rolearnlist_from_ssm_list = rolearnlist_from_ssm['Parameter']['Value'].split(",")
    rolearnlist = rolearnlist_from_ssm_list
    # ----------------------------------------------------------------------------------
    # Get the list of External IDs of cross-account IAM roles saved in SSM Parameter crossAccountExternalIDList
    # ----------------------------------------------------------------------------------
    externalidlist = []
    externalidlist_from_ssm = ssm_client.get_parameter(Name='crossAccountExternalIDList')
    externalidlist_from_ssm_list = externalidlist_from_ssm['Parameter']['Value'].split(",")
    externalidlist = externalidlist_from_ssm_list
    # ----------------------------------------------------------------------------------
    # Get the list of friendly AWS Account Names ('accounting', 'hr', 'development', etc.) for the cross-account IAM roles saved in SSM crossAccountCustomerNameList
    # ----------------------------------------------------------------------------------
    customernamelist = []
    customernamelist_from_ssm = ssm_client.get_parameter(Name='crossAccountCustomerNameList')
    customernamelist_from_ssm_list = customernamelist_from_ssm['Parameter']['Value'].split(",")
    customernamelist = customernamelist_from_ssm_list
    # ----------------------------------------------------------------------------------
    # Loop through the list of ARNs and External IDs, asynchronously invoke slave lambda functions, passing ARN
    # ----------------------------------------------------------------------------------
    for account in range(len(rolearnlist)):
        currentAccount = {"ARN": rolearnlist[account], "externalId": externalidlist[account], "customerName": customernamelist[account]}
    # ----------------------------------------------------------------------------------
    # Invoke child lambda scripts against each account in the SSM list
    # ----------------------------------------------------------------------------------
        invoke_response = client.invoke(FunctionName="createCostExplorerReport",
                                        InvocationType='Event',
                                        Payload=json.dumps(currentAccount))
        print(invoke_response)
        invoke_response = client.invoke(FunctionName="getOrphanEIPs",
                                        InvocationType='Event',
                                        Payload=json.dumps(currentAccount))
        print(invoke_response)
