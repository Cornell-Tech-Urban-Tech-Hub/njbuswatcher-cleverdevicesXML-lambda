import json
from NJTransitAPI import get_xml_data, parse_xml_getBusesForRouteAll
import pandas as pd
import boto3
import datetime as dt

# ARN buswatcher credentials -- verified work on desktop using below code
aws_access_key_id="AKIA2HT76ZARVCBKVT2E"
aws_secret_access_key="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"

# S3 settings
aws_region_name='us-east-2'
aws_bucket_name='bus-observatory' # data will be stored in a systemID bucket under this


def lambda_handler(event, context):
    
    # construct url from passed system_id request (no underscores for S3 bucket names)
    # call the function with the keyword args http://aws.url/-------?systemID=nyct-mta-bus  
    # systemID = event['queryStringParameters']['systemID']
    systemID = "njtransit_bus"
    
    # fetch XML positions
    # print(f"{dt.datetime.now()}\t Fetching buses from {systemID}")
    data, fetch_timestamp = get_xml_data('nj','all_buses')

    # convert feed (list of bus object instances) to a dataframe
    # https://stackoverflow.com/questions/47623014/converting-a-list-of-objects-to-a-pandas-dataframe
    positions = pd.DataFrame([vars(bus) for bus in parse_xml_getBusesForRouteAll(data)])
    positions['timestamp'] = fetch_timestamp
    positions = positions.drop(['name','bus'], axis=1) 
    positions[["lat", "lon"]] = positions[["lat", "lon"]].apply(pd.to_numeric)
    # print(f"{fetch_timestamp}\t Fetched {len(positions)} buses from {systemID}")
    # print(f"{fetch_timestamp}\t Converted {len(positions)} buses into dataframe of shape {positions.shape}")
      
    # dump to instance ephemeral storage 
    filename=f"{systemID}_{fetch_timestamp}.parquet".replace(" ", "_").replace(":", "_")
    # times'ms' per https://stackoverflow.com/questions/63194941/athena-returns-wrong-values-for-timestamp-fields-in-parquet-files
    positions.to_parquet(f"/tmp/{filename}", times='int96')

    # upload dump_file to S3
    source_path=f"/tmp/{filename}" 
    remote_path=f"{systemID}/{filename}"  
    session = boto3.Session(
        region_name=aws_region_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key)
    s3 = session.resource('s3')
    result = s3.Bucket(aws_bucket_name).upload_file(source_path,remote_path)
    outpath = f"s3://{aws_bucket_name}/{remote_path}"
    outmessage = f"lambda-buswatcher-acquire-gtfs-realtime: Dumped {len(positions)} records to {outpath}"

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": outmessage
        }),
    }