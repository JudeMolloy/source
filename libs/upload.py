import boto3
import uuid
import os

from werkzeug.utils import secure_filename

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_BUCKET_NAME = os.environ.get("AWS_BUCKET_NAME")

CF_CDN_FILE = os.environ.get("CF_CDN_FILE")

ALLOWED_FILE_EXT = ['png', 'jpg', 'jpeg']

# Establish s3 client
s3 = boto3.client('s3',
                  aws_access_key_id=AWS_ACCESS_KEY_ID,
                  aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                  )


def upload_file_to_bucket(file, folder):
    unique = str(uuid.uuid4())
    split_name = file.filename.split(".")
    name = split_name[0]
    file_ext = split_name[1]

    # COULD ADD A FILE TYPE CHECK HERE. MIGHT LEAVE THIS FOR SIMPLICITY JUST NOW.
    if file_ext not in ALLOWED_FILE_EXT:
        print("uploaded file not allowed")
        # The following is the default img.
        return "https://www.gravatar.com/avatar/?d=identicon"

    unique_name = secure_filename(unique + "-" + name)  # Generates unique name.
    unique_filename = unique_name + "." + file_ext  # Generates image filename.

    file.save(unique_filename)

    key = folder + "/" + unique_filename  # Uploads into specific folder to trigger the AWS Lambda function.
    s3.upload_file(
        Bucket=str(AWS_GENERAL_BUCKET_NAME),
        Filename=unique_filename,
        Key=key
    )

    # Remove the file from the local file system after uploading to s3.
    os.remove(unique_filename)
    # Generates the link to the cdn which the frontend can uses to pull the on demand video.
    cdn_link = str(CF_CDN_FILE) + key

    return cdn_link