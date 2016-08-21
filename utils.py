#encoding:utf-8

import re
import sys
import datetime
import htmlentitydefs as html_entities

from urllib import unquote
from decimal import Decimal
from importlib import import_module
from functools import total_ordering, wraps

RAW = "raw"
FILE = "file"
FIELD = "field"
DEFAULT_CHARSET = 'utf-8'
FILE_UPLOAD_MAX_MEMORY_SIZE = 2621440  # i.e. 2.5 MB

_PROTECTED_TYPES = (type(None), int, long, float, Decimal,
    datetime.datetime, datetime.date, datetime.time)

class uWsgiUnicodeDecodeError(UnicodeDecodeError):
    def __init__(self, obj, *args):
        self.obj = obj
        UnicodeDecodeError.__init__(self, *args)

    def __str__(self):
        original = UnicodeDecodeError.__str__(self)
        return '%s. You passed in %r (%s)' % (original, self.obj,
                type(self.obj))

class Promise(object):
    """
    This is just a base class for the proxy class created in
    the closure of the lazy function. It can be used to recognize
    promises in code.
    """
    pass

def parse_boundary_stream(stream, max_header_size):
    """
    Parses one and exactly one stream that encapsulates a boundary.
    """
    # Stream at beginning of header, look for end of header
    # and parse it if found. The header must fit within one
    # chunk.
    chunk = stream.read(max_header_size)

    # 'find' returns the top of these four bytes, so we'll
    # need to munch them later to prevent them from polluting
    # the payload.
    header_end = chunk.find(b'\r\n\r\n')

    def _parse_header(line):
        main_value_pair, params = parse_header(line)
        try:
            name, value = main_value_pair.split(':', 1)
        except ValueError:
            raise ValueError("Invalid header: %r" % line)
        return name, (value, params)

    if header_end == -1:
        # we find no header, so we just mark this fact and pass on
        # the stream verbatim
        stream.unget(chunk)
        return (RAW, {}, stream)

    header = chunk[:header_end]

    # here we place any excess chunk back onto the stream, as
    # well as throwing away the CRLFCRLF bytes from above.
    stream.unget(chunk[header_end + 4:])

    TYPE = RAW
    outdict = {}

    # Eliminate blank lines
    for line in header.split(b'\r\n'):
        # This terminology ("main value" and "dictionary of
        # parameters") is from the Python docs.
        try:
            name, (value, params) = _parse_header(line)
        except ValueError:
            continue

        if name == 'content-disposition':
            TYPE = FIELD
            if params.get('filename'):
                TYPE = FILE

        outdict[name] = value, params

    if TYPE == RAW:
        stream.unget(chunk)

    return (TYPE, outdict, stream)

def parse_header(line):
    """
    将http请求行中的key=value解析为字典
    """
    plist = _parse_header_params(b';' + line)   #按分号把一行分割成多个字段，为什么不是split(;)?请看_parse_header_params的注释
    key = plist.pop(0).lower().decode('ascii')
    pdict = {}
    for p in plist:
        i = p.find(b'=')
        if i >= 0:
            has_encoding = False
            name = p[:i].strip().lower().decode('ascii')
            if name.endswith('*'):
                # Lang/encoding embedded in the value (like "filename*=UTF-8''file.ext")
                # http://tools.ietf.org/html/rfc2231#section-4
                name = name[:-1]
                if p.count(b"'") == 2:  #根据单引号数量判断是否指定了value的编码
                    has_encoding = True
                    
            value = p[i + 1:].strip()
            if has_encoding:    #如果指定了encoding,此进行解码
                encoding, lang, value = value.split(b"'")
                value = unquote(value).decode(encoding)
            
            #正则表达式相关，处理转义字符
            if len(value) >= 2 and value[:1] == value[-1:] == b'"':
                value = value[1:-1]
                value = value.replace(b'\\\\', b'\\').replace(b'\\"', b'"')
                
            pdict[name] = value
            
    return key, pdict


def _parse_header_params(s):
    '''
    按分号把http的一个请求行分割成数组
    '''
    plist = []
    while s[:1] == b';': #为什么不是s[0]？估计是因为s[0]会在s为空的报错，s[:1]不会
        s = s[1:]
        end = s.find(b';')
        #防止把一对双引号中通过分号分开，比如afafa;"dafafaf;dfafaf";dfafa中的第二个分号就不能当作分割符号
        while end > 0 and s.count(b'"', 0, end) % 2:
            end = s.find(b';', end + 1)
        if end < 0:
            end = len(s)
        f = s[:end]
        plist.append(f.strip())
        s = s[end:]
    return plist


def is_protected_type(obj):
    """Determine if the object instance is of a protected type.

    Objects of protected types are preserved as-is when passed to
    force_text(strings_only=True).
    """
    return isinstance(obj, _PROTECTED_TYPES)



def six_iteritems(d, **kw):
    return d.iteritems(**kw)

def six_iterlists(d, **kw):
    return d.iterlists(**kw)

def six_itervalues(d, **kw):
    return d.itervalues(**kw)

def bytes_to_text(s, encoding):
    """
    将basestring对象转换成指定编码的unicode对象，非法字符用"unknown"(\ufffd)代替
    """
    if isinstance(s, bytes):
        return unicode(s, encoding, 'replace')
    else:
        return s

def force_bytes(s, encoding='utf-8', strings_only=False, errors='strict'):
    # Handle the common case first for performance reasons.
    if isinstance(s, bytes):
        if encoding == 'utf-8':
            return s
        else:
            return s.decode('utf-8', errors).encode(encoding, errors)
    if strings_only and is_protected_type(s):
        return s
    if isinstance(s, buffer):
        return bytes(s)
    if isinstance(s, Promise):
        return unicode(s).encode(encoding, errors)
    if not isinstance(s, basestring):
        try:
            return bytes(s)
        except UnicodeEncodeError:
            if isinstance(s, Exception):
                # An Exception subclass containing non-ASCII data that doesn't
                # know how to print itself properly. We shouldn't raise a
                # further exception.
                return b' '.join(force_bytes(arg, encoding, strings_only, errors)
                                 for arg in s)
            return unicode(s).encode(encoding, errors)
    else:
        return s.encode(encoding, errors)

def force_text(s, encoding='utf-8', strings_only=False, errors='strict'):
    """
    将s按照指定的encoding转换成字符串，如果指定strings_only=True，则忽略s中的非string-like类型
    的属性，如果s中有迭代器则也穷尽所有值进行转换
    """
    # Handle the common case first for performance reasons.
    if isinstance(s, unicode):
        return s
    if strings_only and is_protected_type(s):
        return s
    try:
        if not isinstance(s, basestring):
            if hasattr(s, '__unicode__'):
                s = unicode(s)
            else:
                s = unicode(bytes(s), encoding, errors)
        else:
            # Note: We use .decode() here, instead of six.text_type(s, encoding,
            # errors), so that if s is a SafeBytes, it ends up being a
            # SafeText at the end.
            s = s.decode(encoding, errors)
    except UnicodeDecodeError as e:
        if not isinstance(s, Exception):
            raise uWsgiUnicodeDecodeError(s, *e.args)
        else:
            # If we get to here, the caller has passed in an Exception
            # subclass populated with non-ASCII bytestring data without a
            # working unicode method. Try to handle this without raising a
            # further exception by individually forcing the exception args
            # to unicode.
            s = ' '.join(force_text(arg, encoding, strings_only, errors)
                         for arg in s)
    return s

def _replace_entity(match):
    text = match.group(1)
    if text[0] == '#':
        text = text[1:]
        try:
            if text[0] in 'xX':
                c = int(text[1:], 16)
            else:
                c = int(text)
            return unichr(c)
        except ValueError:
            return match.group(0)
    else:
        try:
            return unichr(html_entities.name2codepoint[text])
        except (ValueError, KeyError):
            return match.group(0)
        
_entity_re = re.compile(r"&(#?[xX]?(?:[0-9a-fA-F]+|\w{1,8}));")

def lazy(func, *resultclasses):
    """
    Turns any callable into a lazy evaluated callable. You need to give result
    classes or types -- at least one is needed so that the automatic forcing of
    the lazy evaluation code is triggered. Results are not memoized; the
    function is evaluated on every access.
    """

    @total_ordering
    class __proxy__(Promise):
        """
        Encapsulate a function call and act as a proxy for methods that are
        called on the result of that function. The function is not evaluated
        until one of the methods on the result is called.
        """
        __prepared = False

        def __init__(self, args, kw):
            self.__args = args
            self.__kw = kw
            if not self.__prepared:
                self.__prepare_class__()
            self.__prepared = True

        def __reduce__(self):
            return (
                _lazy_proxy_unpickle,
                (func, self.__args, self.__kw) + resultclasses
            )

        @classmethod
        def __prepare_class__(cls):
            for resultclass in resultclasses:
                for type_ in resultclass.mro():
                    for method_name in type_.__dict__.keys():
                        # All __promise__ return the same wrapper method, they
                        # look up the correct implementation when called.
                        if hasattr(cls, method_name):
                            continue
                        meth = cls.__promise__(method_name)
                        setattr(cls, method_name, meth)
            cls._delegate_bytes = bytes in resultclasses
            cls._delegate_text = unicode in resultclasses
            assert not (cls._delegate_bytes and cls._delegate_text), (
                "Cannot call lazy() with both bytes and text return types.")
            if cls._delegate_text:
                cls.__unicode__ = cls.__text_cast
                cls.__str__ = cls.__bytes_cast_encoded
            elif cls._delegate_bytes:
                cls.__str__ = cls.__bytes_cast

        @classmethod
        def __promise__(cls, method_name):
            # Builds a wrapper around some magic method
            def __wrapper__(self, *args, **kw):
                # Automatically triggers the evaluation of a lazy value and
                # applies the given magic method of the result type.
                res = func(*self.__args, **self.__kw)
                return getattr(res, method_name)(*args, **kw)
            return __wrapper__

        def __text_cast(self):
            return func(*self.__args, **self.__kw)

        def __bytes_cast(self):
            return bytes(func(*self.__args, **self.__kw))

        def __bytes_cast_encoded(self):
            return func(*self.__args, **self.__kw).encode('utf-8')

        def __cast(self):
            if self._delegate_bytes:
                return self.__bytes_cast()
            elif self._delegate_text:
                return self.__text_cast()
            else:
                return func(*self.__args, **self.__kw)

        def __ne__(self, other):
            if isinstance(other, Promise):
                other = other.__cast()
            return self.__cast() != other

        def __eq__(self, other):
            if isinstance(other, Promise):
                other = other.__cast()
            return self.__cast() == other

        def __lt__(self, other):
            if isinstance(other, Promise):
                other = other.__cast()
            return self.__cast() < other

        def __hash__(self):
            return hash(self.__cast())

        def __mod__(self, rhs):
            if self._delegate_bytes:
                return bytes(self) % rhs
            elif self._delegate_text:
                return unicode(self) % rhs
            return self.__cast() % rhs

        def __deepcopy__(self, memo):
            # Instances of this class are effectively immutable. It's just a
            # collection of functions. So we don't need to do anything
            # complicated for copying.
            memo[id(self)] = self
            return self

    @wraps(func)
    def __wrapper__(*args, **kw):
        # Creates the proxy object, instead of the actual value.
        return __proxy__(args, kw)

    return __wrapper__

def _lazy_proxy_unpickle(func, args, kwargs, *resultclasses):
    return lazy(func, *resultclasses)(*args, **kwargs)


def allow_lazy(func, *resultclasses):
    """
    A decorator that allows a function to be called with one or more lazy
    arguments. If none of the args are lazy, the function is evaluated
    immediately, otherwise a __proxy__ is returned that will evaluate the
    function when needed.
    """
    lazy_func = lazy(func, *resultclasses)

    @wraps(func)
    def wrapper(*args, **kwargs):
        for arg in list(args) + list(six_itervalues(kwargs)):
            if isinstance(arg, Promise):
                break
        else:
            return func(*args, **kwargs)
        return lazy_func(*args, **kwargs)
    return wrapper

def unescape_entities(text):
    return _entity_re.sub(_replace_entity, text)
unescape_entities = allow_lazy(unescape_entities, unicode)

def python_2_unicode_compatible(klass):
    """
    A decorator that defines __unicode__ and __str__ methods under Python 2.
    Under Python 3 it does nothing.

    To support Python 2 and 3 with a single code base, define a __str__ method
    returning text and apply this decorator to the class.
    """
    
    if '__str__' not in klass.__dict__:
        raise ValueError("@python_2_unicode_compatible cannot be applied "
                         "to %s because it doesn't define __str__()." %
                         klass.__name__)
    klass.__unicode__ = klass.__str__
    klass.__str__ = lambda self: self.__unicode__().encode('utf-8')
    
    return klass

def import_string(dotted_path):
    """
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.
    """
    try:
        module_path, class_name = dotted_path.rsplit('.', 1)
    except ValueError:
        msg = "%s doesn't look like a module path" % dotted_path
        raise ImportError, ImportError(msg), sys.exc_info()[2]

    module = import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError:
        msg = 'Module "%s" does not define a "%s" attribute/class' % (
            module_path, class_name)
        raise ImportError, ImportError(msg), sys.exc_info()[2]

