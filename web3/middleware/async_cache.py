from concurrent.futures import (
    ThreadPoolExecutor,
)
import threading
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Collection,
)

from web3._utils.async_caching import (
    async_lock,
)
from web3._utils.caching import (
    generate_cache_key,
)
from web3.middleware.cache import (
    SIMPLE_CACHE_RPC_WHITELIST,
    _should_cache_response,
)
from web3.types import (
    AsyncMiddleware,
    Middleware,
    RPCEndpoint,
    RPCResponse,
)
from web3.utils.caching import (
    SimpleCache,
)

if TYPE_CHECKING:
    from web3 import Web3  # noqa: F401

_async_request_thread_pool = ThreadPoolExecutor()


async def async_construct_simple_cache_middleware(
    cache: SimpleCache = None,
    rpc_whitelist: Collection[RPCEndpoint] = SIMPLE_CACHE_RPC_WHITELIST,
    should_cache_fn: Callable[
        [RPCEndpoint, Any, RPCResponse], bool
    ] = _should_cache_response,
) -> Middleware:
    """
    Constructs a middleware which caches responses based on the request
    ``method`` and ``params``

    :param cache: A ``SimpleCache`` class.
    :param rpc_whitelist: A set of RPC methods which may have their responses cached.
    :param should_cache_fn: A callable which accepts ``method`` ``params`` and
        ``response`` and returns a boolean as to whether the response should be
        cached.
    """
    if cache is None:
        cache = SimpleCache(256)

    async def async_simple_cache_middleware(
        make_request: Callable[[RPCEndpoint, Any], Any], _async_w3: "Web3"
    ) -> AsyncMiddleware:
        lock = threading.Lock()

        async def middleware(method: RPCEndpoint, params: Any) -> RPCResponse:
            if method in rpc_whitelist:
                async with async_lock(_async_request_thread_pool, lock):
                    cache_key = generate_cache_key(
                        f"{threading.get_ident()}:{(method, params)}"
                    )
                    if cache.__contains__(cache_key):
                        return cache.get_cache_entry(cache_key)

                    response = await make_request(method, params)
                    if should_cache_fn(method, params, response):
                        cache.cache(cache_key, response)
                    return response
            else:
                return await make_request(method, params)

        return middleware

    return async_simple_cache_middleware


async def _async_simple_cache_middleware(
    make_request: Callable[[RPCEndpoint, Any], Any], async_w3: "Web3"
) -> Middleware:
    middleware = await async_construct_simple_cache_middleware()
    return await middleware(make_request, async_w3)
