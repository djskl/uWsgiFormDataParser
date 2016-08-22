代码直接取自Django，删除了其中对Django其他包和模块的依赖，并对部分代码添加了注释。

例子：
```
#wsgi.py，定义uwsgi application

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

```
uwsgi --module wsgi --http :80  #启动uwsgi服务器
```

```
#借助requests测试表单数据提交
import requests

params = {
    "msg": "hello,world"          
}

files = {'mfy': open('/root/jp.png', 'rb')}

requests.post("http://127.0.0.1", data=params, files=files)
```
