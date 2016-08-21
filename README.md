解析前端提交的multipart/form-data类型的form数据，生成类似于Django的request。

代码取自Django并附详细注释(注释部分不断更新)，可直接在普通的uWSGI应用中使用：
```
#wsgi.py
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
```

