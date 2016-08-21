'''
Created on Aug 20, 2016

@author: root
'''
from multipartparser import MultiPartParser
from datastructures import ImmutableList
from files.uploadhandler import MemoryFileUploadHandler,\
    TemporaryFileUploadHandler

def parse_form_data(env):
    upload_handlers = ImmutableList(
        [MemoryFileUploadHandler(),TemporaryFileUploadHandler()],
        warning="You cannot alter upload handlers after the upload has been processed."
    )
    parser = MultiPartParser(env, upload_handlers)
    return parser.parse()

def application(env, sr):
    
    params = parse_form_data(env)
    
    print params
    
    sr("200 OK", [("Content-Type", "text/html")])
    
    return "OK"
    
    
