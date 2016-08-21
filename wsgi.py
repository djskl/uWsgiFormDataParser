'''
Created on Aug 20, 2016

@author: root
'''
from multipartparser import MultiPartParser
from datastructures import ImmutableList
from files.uploadhandler import MemoryFileUploadHandler,\
    TemporaryFileUploadHandler
import os

def parse_form_data(env):
    upload_handlers = ImmutableList(
        [MemoryFileUploadHandler(),TemporaryFileUploadHandler()],
        warning="You cannot alter upload handlers after the upload has been processed."
    )
    parser = MultiPartParser(env, upload_handlers)
    return parser.parse()

def application(env, sr):
    
    params, files = parse_form_data(env)
    
    print params, files
    
    upload_file = files["mfy"]
    
    filename = upload_file.name
    
    with open(os.path.join("/tmp", filename), "w") as writer:
        for chunk in upload_file.chunks():
            writer.write(chunk)
    
    sr("200 OK", [("Content-Type", "text/html")])
    
    return "OK"
    
    
