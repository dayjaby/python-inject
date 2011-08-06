'''Scopes configure how objects are reused.

ApplicationScope has bindings for the whole application.
ThreadScope stores instances for each thread.
RequestScope stores 
'''
import logging
import threading
from inject.exc import NoRequestError, FactoryNotCallable


class AbstractScope(object):
    
    '''Abstract scope.
    
    Subclassing: set the _bindings attribute in the constructor to
        any object which supports the base dict interface.
    '''
    
    logger = None
    
    def __init__(self):
        self._factories = {}
    
    def __contains__(self, type):
        return self.is_bound(type)
    
    def bind(self, type, to):
        if self.is_bound(type):
            self.logger.info('Overriding an existing binding for type=%r.',
                             type)
            self.unbind(type)
        
        self._bindings[type] = to
        self.logger.info('Bound %r to %r.', type, to)
    
    def unbind(self, type):
        if type in self._bindings:
            del self._bindings[type]
            self.logger.info('Unbound %r.', type)
    
    def is_bound(self, type):
        return type in self._bindings
    
    def bind_factory(self, type, factory):
        if not callable(factory):
            raise FactoryNotCallable(factory)
        
        self.unbind_factory(type)
        self._factories[type] = factory
    
    def unbind_factory(self, type):
        if type in self._factories:
            del self._factories[type]
            self.logger.info('Unbound factory for %r.', type)
    
    def is_factory_bound(self, type):
        return type in self._factories
    
    def get(self, type):
        if type in self._bindings:
            return self._bindings.get(type)
        
        elif type in self._factories:
            factory = self._factories[type]
            inst = factory()
            self.bind(type, inst)
            return inst


class ApplicationScope(AbstractScope):
    
    '''ApplicationScope scope caches instances for an application (a process).
    It can be called a singleton scope.
    '''
    
    logger = logging.getLogger('inject.ApplicationScope')
    
    def __init__(self):
        super(ApplicationScope, self).__init__()
        
        self._bindings = {}
        self.bind(ApplicationScope, self)


class ThreadLocalBindings(threading.local):
    
    def __init__(self):
        self._data = {}
    
    def __getitem__(self, key):
        return self._data[key]
    
    def __setitem__(self, key, value):
        self._data[key] = value
    
    def __delitem__(self, key):
        del self._data[key]
    
    def __contains__(self, key):
        return key in self._data
    
    def get(self, key):
        return self._data.get(key)
    
    def __len__(self):
        return len(self._data)
    
    def clear(self):
        self._data = {}


class ThreadScope(AbstractScope):
    
    '''ThreadScope is a thread-local scope.'''
    
    logger = logging.getLogger('inject.ThreadScope')
    
    def __init__(self):
        super(ThreadScope, self).__init__()
        self._bindings = ThreadLocalBindings()


class RequestLocalBindings(ThreadLocalBindings):
    
    def __init__(self):
        super(RequestLocalBindings, self).__init__()
        self.request_started = False
    
    def start_request(self):
        self.request_started = True
    
    def end_request(self):
        self.clear()
        self.request_started = False


class RequestScope(ThreadScope):
    
    '''RequestScope is a request-local thread-local scope which supports
    the context manager protocol (the with statement, 2.5+) or must
    be explicitly started/ended for every request.
    
    To use it start and end the requests, usually using the with statement,
    or try/finally.
    WSGI example::
    
        @inject.param('scope', RequestScope)
        def python25(environ, startresponse, scope):
            with scope:
                startresponse()
                return 'Response'
        
        @inject.param('scope', RequestScope)
        def python24(environ, startresponse, scope):
            scope.start()
            try:
                startresponse()
                return 'Response'
            finally:
                scope.end()
    
    '''
    
    logger = logging.getLogger('inject.RequestScope')
    
    def __init__(self):
        super(RequestScope, self).__init__()
        self._bindings = RequestLocalBindings()
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end()
        return False
    
    def start(self):
        '''Start a new request.'''
        self._bindings.start_request()
    
    def end(self):
        '''End the request and clear the bindings.'''
        self._bindings.end_request()
    
    def bind(self, type, to):
        self._request_required()
        return super(RequestScope, self).bind(type, to)
    
    def unbind(self, type):
        self._request_required()
        return super(RequestScope, self).unbind(type)

    def get(self, type):
        self._request_required()
        return super(RequestScope, self).get(type)
    
    def _request_required(self):
        if not self._bindings.request_started:
            raise NoRequestError()


appscope = ApplicationScope
threadscope = ThreadScope
reqscope = RequestScope