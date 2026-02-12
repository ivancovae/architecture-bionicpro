"""Main FastAPI application for auth_proxy service."""

import logging
import secrets
import time
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager
from urllib.parse import urlencode

import httpx
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse

from config import settings
from keycloak_client import keycloak_client
from models import ProxyRequest, SessionData, UserInfo
from session_manager import session_manager

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Обработчик lifespan для инициализации и очистки ресурсов."""
    # Startup
    logger.info("Starting auth_proxy service...")
    await session_manager.connect()
    logger.info("Connected to Redis")

    yield

    # Shutdown
    logger.info("Shutting down auth_proxy service...")
    await session_manager.disconnect()
    logger.info("Disconnected from Redis")


# Создание FastAPI приложения с lifespan
app = FastAPI(title="Auth Proxy Service", lifespan=lifespan)

# Добавление CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,  # URL фронтенда
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # React dev server
    ],
    allow_credentials=True,  # Разрешаем передачу cookies
    allow_methods=["*"],  # Разрешаем все HTTP методы
    allow_headers=["*"],  # Разрешаем все заголовки
)


async def get_session_from_cookie(
    session_id: Optional[str] = Cookie(None, alias=settings.session_cookie_name)
) -> Optional[SessionData]:
    """
    Dependency для получения данных сессии из cookie.

    Args:
        session_id: Session ID из cookie

    Returns:
        SessionData или None, если сессия не найдена
    """
    if not session_id:
        return None

    session_data = await session_manager.get_session(session_id)
    return session_data


@app.get("/user_info")
async def user_info(
    session_data: Optional[SessionData] = Depends(get_session_from_cookie),
    session_id: Optional[str] = Cookie(None, alias=settings.session_cookie_name),
) -> UserInfo:
    """
    Эндпоинт для получения информации о пользователе.

    Returns:
        UserInfo с информацией о пользователе или статусом авторизации
    """
    # Проверяем наличие session cookie
    has_session_cookie = session_id is not None

    # Если нет сессии, проверяем, была ли выставлена session_id
    if not session_data:
        # Если session_id была выставлена, но оказалась невалидной - это подозрительно
        if session_id:
            # Возможная утечка session_id или session hijacking
            logger.warning(f"Invalid session_id detected in /user_info: {session_id[:20]}... - possible session hijacking or leaked session_id")
            raise HTTPException(
                status_code=409,
                detail="Session ID выставлена, но не валидна. Возможна утечка session_id или попытка перехвата сессии. Пожалуйста, выйдите и войдите заново."
            )
        
        return UserInfo(has_session_cookie=has_session_cookie, is_authorized=False)

    # Проверяем, не истек ли access token
    current_time = int(time.time())
    if current_time >= session_data.expires_at:
        # Пытаемся обновить токен
        try:
            token_response = await keycloak_client.refresh_access_token(session_data.refresh_token)

            # Обновляем данные сессии
            session_data.access_token = token_response["access_token"]
            session_data.refresh_token = token_response["refresh_token"]
            session_data.expires_at = current_time + token_response["expires_in"]

            await session_manager.update_session(session_data)

        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            # Если не удалось обновить токен, удаляем сессию
            await session_manager.delete_session(session_data.session_id)
            return UserInfo(has_session_cookie=has_session_cookie, is_authorized=False)

    # Декодируем access token для получения информации о пользователе
    try:
        payload = await keycloak_client.verify_token(session_data.access_token)

        # Извлекаем информацию из токена
        return UserInfo(
            has_session_cookie=True,
            is_authorized=True,
            username=payload.get("preferred_username"),
            email=payload.get("email"),
            first_name=payload.get("given_name"),
            last_name=payload.get("family_name"),
            realm_roles=payload.get("realm_roles") or payload.get("realm_access", {}).get("roles", []),
            permissions=payload.get("resource_access"),
            sub=payload.get("sub"),
            external_uuid=payload.get("external_uuid"),  # UUID из LDAP (для LDAP-пользователей)
        )
    except Exception as e:
        logger.error(f"Failed to verify token: {e}")
        # Если токен невалиден, удаляем сессию
        await session_manager.delete_session(session_data.session_id)
        return UserInfo(has_session_cookie=has_session_cookie, is_authorized=False)


@app.get("/sign_in")
async def sign_in(
    request: Request,
    session_data: Optional[SessionData] = Depends(get_session_from_cookie),
    redirect_to: Optional[str] = None,
):
    """
    Эндпоинт для начала процесса авторизации.

    Args:
        redirect_to: URL для редиректа после успешной авторизации

    Returns:
        Редирект на страницу авторизации Keycloak или 200 OK, если уже авторизован
    """
    # Если пользователь уже авторизован, возвращаем 200 OK
    if session_data:
        return JSONResponse({"status": "already_authenticated"})

    # Генерируем state для защиты от CSRF
    state = secrets.token_urlsafe(32)

    # Формируем callback URL
    callback_url = str(request.url_for("callback"))

    # Получаем URL для авторизации с PKCE
    auth_url, code_verifier = keycloak_client.get_authorization_url(redirect_uri=callback_url, state=state)

    # Сохраняем state, redirect_to и code_verifier в Redis (для проверки в callback)
    state_key = f"oauth_state:{state}"
    state_data = {
        "redirect_to": redirect_to or settings.frontend_public_url,  # Используем публичный URL
        "code_verifier": code_verifier,  # Сохраняем для PKCE
        "created_at": int(time.time()),
    }
    await session_manager.redis_client.setex(state_key, 300, str(state_data))  # TTL 5 минут

    logger.info(f"Redirecting to Keycloak with PKCE, state={state[:10]}...")
    logger.info(f"Auth URL: {auth_url[:100]}...")

    # Редиректим пользователя на страницу авторизации Keycloak
    return RedirectResponse(url=auth_url)


@app.get("/callback")
async def callback(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """
    Callback эндпоинт для завершения OIDC flow.

    Args:
        code: Authorization code от Keycloak
        state: State параметр для защиты от CSRF
        error: Ошибка авторизации (если есть)

    Returns:
        Редирект на фронтенд с установленным session cookie
    """
    # Проверяем наличие ошибки
    if error:
        logger.error(f"Authorization error: {error}")
        return RedirectResponse(url=f"{settings.frontend_public_url}?error={error}")

    # Проверяем наличие code и state
    if not code or not state:
        logger.error("Missing code or state in callback")
        return RedirectResponse(url=f"{settings.frontend_public_url}?error=missing_parameters")

    # Проверяем state (защита от CSRF)
    state_key = f"oauth_state:{state}"
    state_data_str = await session_manager.redis_client.get(state_key)

    if not state_data_str:
        logger.error("Invalid or expired state")
        return RedirectResponse(url=f"{settings.frontend_public_url}?error=invalid_state")

    # Удаляем state из Redis
    await session_manager.redis_client.delete(state_key)

    # Парсим state_data
    import ast

    state_data = ast.literal_eval(state_data_str)
    redirect_to = state_data.get("redirect_to", settings.frontend_public_url)
    code_verifier = state_data.get("code_verifier")  # Получаем code_verifier для PKCE

    # Обмениваем code на токены с PKCE
    try:
        callback_url = str(request.url_for("callback"))
        token_response = await keycloak_client.exchange_code_for_tokens(
            code=code, redirect_uri=callback_url, code_verifier=code_verifier  # Передаем code_verifier для PKCE
        )
        logger.info("Successfully exchanged code for tokens with PKCE")
    except Exception as e:
        logger.error(f"Failed to exchange code for tokens: {e}")
        return RedirectResponse(url=f"{settings.frontend_public_url}?error=token_exchange_failed")

    # Декодируем access token для получения информации о пользователе
    try:
        access_token = token_response["access_token"]
        logger.info(f"Attempting to verify token for callback, token length: {len(access_token)}")
        payload = await keycloak_client.verify_token(access_token)

        user_id = payload["sub"]
        username = payload.get("preferred_username", "unknown")
        logger.info(f"Token verified successfully for user: {username} (user_id: {user_id})")

    except Exception as e:
        logger.error(f"Failed to verify token: {e}", exc_info=True)
        return RedirectResponse(url=f"{settings.frontend_public_url}?error=invalid_token")

    # Создаем сессию
    expires_at = int(time.time()) + token_response.get("expires_in", 300)
    session_id = await session_manager.create_session(
        user_id=user_id,
        username=username,
        access_token=token_response["access_token"],
        refresh_token=token_response["refresh_token"],
        expires_at=expires_at,
    )

    # Создаём HTML-страницу для очистки Keycloak cookies через JavaScript
    # Это необходимо, так как FastAPI не может удалить cookies с другим path
    keycloak_cookies = [
        "AUTH_SESSION_ID",
        "AUTH_SESSION_ID_LEGACY",
        "KC_RESTART",
        "KC_AUTH_SESSION_HASH",
        "KEYCLOAK_SESSION",
        "KEYCLOAK_SESSION_LEGACY",
        "KEYCLOAK_IDENTITY",
        "KEYCLOAK_IDENTITY_LEGACY",
    ]
    
    # Генерируем JavaScript для удаления cookies
    # Удаляем cookies с разными path, так как Keycloak может устанавливать их с разными путями
    delete_cookies_js_lines = []
    for cookie_name in keycloak_cookies:
        # Удаляем с path /realms/{realm}/
        delete_cookies_js_lines.append(
            f'document.cookie = "{cookie_name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/realms/{settings.keycloak_realm}/; domain=localhost";'
        )
        # Удаляем с path /realms/{realm} (без слэша в конце)
        delete_cookies_js_lines.append(
            f'document.cookie = "{cookie_name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/realms/{settings.keycloak_realm}; domain=localhost";'
        )
        # Удаляем с path / (на всякий случай)
        delete_cookies_js_lines.append(
            f'document.cookie = "{cookie_name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=localhost";'
        )
    
    delete_cookies_js = "\n            ".join(delete_cookies_js_lines)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Redirecting...</title>
        <script>
            // Удаляем Keycloak cookies
            {delete_cookies_js}
            
            // Редиректим на фронтенд
            window.location.href = "{redirect_to}";
        </script>
    </head>
    <body>
        <p>Redirecting...</p>
    </body>
    </html>
    """
    
    # Создаём HTML response и устанавливаем session cookie через заголовки
    response = HTMLResponse(content=html_content)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=settings.session_lifetime_seconds,
        httponly=settings.session_cookie_httponly,
        samesite=settings.session_cookie_samesite,
        secure=settings.session_cookie_secure,
        path=settings.session_cookie_path,
        domain=None,
    )
    
    # Удаляем Keycloak cookies через Set-Cookie заголовки
    # Это единственный способ удалить cookies с другим path
    for cookie_name in keycloak_cookies:
        # Удаляем с path /realms/{realm}/
        response.set_cookie(
            key=cookie_name,
            value="",
            max_age=-1,
            expires=0,
            path=f"/realms/{settings.keycloak_realm}/",
            domain=None,
        )
        # Удаляем с path /realms/{realm} (без слэша)
        response.set_cookie(
            key=cookie_name,
            value="",
            max_age=-1,
            expires=0,
            path=f"/realms/{settings.keycloak_realm}",
            domain=None,
        )
    
    logger.info(f"User {username} authenticated successfully")
    return response


@app.post("/sign_out")
@app.get("/sign_out")
async def sign_out(session_data: Optional[SessionData] = Depends(get_session_from_cookie)):
    """
    Эндпоинт для выхода из системы.
    Завершает сессию в Keycloak и удаляет локальную сессию.

    Returns:
        Удаление session cookie и данных сессии из Redis
    """
    # Если есть сессия, завершаем её в Keycloak и удаляем локально
    if session_data:
        # Завершаем сессию в Keycloak используя refresh_token из session_data
        if session_data.refresh_token:
            keycloak_logout_success = await keycloak_client.logout(session_data.refresh_token)

            if keycloak_logout_success:
                logger.info(f"User {session_data.username} logged out from Keycloak")
            else:
                logger.warning(f"Failed to logout user {session_data.username} from Keycloak")

        # Удаляем локальную сессию
        await session_manager.delete_session(session_data.session_id)
        logger.info(f"User {session_data.username} signed out (local session deleted)")

    # Создаем ответ и удаляем session cookie
    response = JSONResponse({"status": "signed_out"})

    # Удаляем cookie установкой expires в прошлое
    response.set_cookie(
        key=settings.session_cookie_name,
        value="",
        max_age=-1,  # Отрицательное значение удаляет cookie
        expires=0,  # Устанавливаем expires в 0
        httponly=settings.session_cookie_httponly,
        samesite=settings.session_cookie_samesite,
        secure=settings.session_cookie_secure,
        path=settings.session_cookie_path,
    )

    return response


@app.api_route("/proxy", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(
    request: Request,
    session_data: Optional[SessionData] = Depends(get_session_from_cookie),
    session_id: Optional[str] = Cookie(None, alias=settings.session_cookie_name),
):
    """
    Эндпоинт для проксирования запросов к upstream сервисам.

    Args:
        request: Входящий HTTP запрос

    Returns:
        Ответ от upstream сервиса
    """
    # Получаем body запроса (для POST/PUT/PATCH) или query params (для GET)
    try:
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.json()
            proxy_request = ProxyRequest(**body)
        else:
            # Для GET запросов используем query параметры
            upstream_uri = request.query_params.get("upstream_uri")
            redirect_to_sign_in = request.query_params.get("redirect_to_sign_in", "false").lower() == "true"
            upstream_method = request.query_params.get("method", "GET").upper()

            if not upstream_uri:
                raise HTTPException(status_code=400, detail="upstream_uri is required")

            proxy_request = ProxyRequest(
                upstream_uri=upstream_uri, method=upstream_method, redirect_to_sign_in=redirect_to_sign_in
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to parse proxy request: {e}")
        raise HTTPException(status_code=400, detail="Invalid request body")

    # Проверяем авторизацию
    if not session_data:
        # Если session_id была выставлена, но оказалась невалидной - это подозрительно
        if session_id:
            # Возможная утечка session_id или session hijacking
            logger.warning(f"Invalid session_id detected: {session_id[:20]}... - possible session hijacking or leaked session_id")
            raise HTTPException(
                status_code=409,
                detail="Session ID выставлена, но не валидна. Возможна утечка session_id или попытка перехвата сессии. Пожалуйста, выйдите и войдите заново."
            )
        
        if proxy_request.redirect_to_sign_in:
            # Редиректим на страницу авторизации
            return RedirectResponse(url="/sign_in")
        else:
            # Возвращаем 401 Unauthorized
            raise HTTPException(status_code=401, detail="Unauthorized")

    # Проверяем, не истек ли access token
    current_time = int(time.time())
    if current_time >= session_data.expires_at:
        # Пытаемся обновить токен
        try:
            token_response = await keycloak_client.refresh_access_token(session_data.refresh_token)

            # Обновляем данные сессии
            session_data.access_token = token_response["access_token"]
            session_data.refresh_token = token_response["refresh_token"]
            session_data.expires_at = current_time + token_response["expires_in"]

            await session_manager.update_session(session_data)

        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            # Если не удалось обновить токен, возвращаем 401
            await session_manager.delete_session(session_data.session_id)

            if proxy_request.redirect_to_sign_in:
                return RedirectResponse(url="/sign_in")
            else:
                raise HTTPException(status_code=401, detail="Token expired")

    # Выполняем ротацию session ID (если включено)
    new_session_id = None
    if settings.enable_session_rotation:
        new_session_id = await session_manager.rotate_session(session_data.session_id)

    # Проксируем запрос к upstream сервису
    try:
        # Получаем все заголовки из исходного запроса
        headers = dict(request.headers)

        # Удаляем заголовки, которые не нужно передавать
        headers.pop("host", None)
        headers.pop("content-length", None)

        # Добавляем Authorization заголовок с JWT токеном
        headers["Authorization"] = f"Bearer {session_data.access_token}"

        # Получаем cookies из исходного запроса
        cookies = dict(request.cookies)

        # Удаляем session cookie (не передаем его upstream)
        cookies.pop(settings.session_cookie_name, None)

        # Определяем тело запроса для upstream
        upstream_body = None
        if proxy_request.method.upper() in ["POST", "PUT", "PATCH"]:
            if proxy_request.body is not None:
                # Если body указан в ProxyRequest, используем его
                import json
                upstream_body = json.dumps(proxy_request.body).encode('utf-8')
                headers["Content-Type"] = "application/json"
            else:
                # Иначе используем тело исходного запроса
                upstream_body = await request.body()

        # Выполняем запрос к upstream (используем метод из proxy_request, а не из входящего запроса)
        async with httpx.AsyncClient() as client:
            upstream_response = await client.request(
                method=proxy_request.method.upper(),  # Используем метод из ProxyRequest
                url=proxy_request.upstream_uri,
                headers=headers,
                cookies=cookies,
                content=upstream_body,
                follow_redirects=False,
            )

        # Получаем заголовки ответа от upstream
        response_headers = dict(upstream_response.headers)

        # Удаляем Authorization заголовок из ответа (если есть)
        response_headers.pop("authorization", None)
        response_headers.pop("Authorization", None)

        # Создаем Response объект
        response = Response(
            content=upstream_response.content, status_code=upstream_response.status_code, headers=response_headers
        )

        # Устанавливаем новый session cookie (если была ротация)
        if new_session_id:
            response.set_cookie(
                key=settings.session_cookie_name,
                value=new_session_id,
                max_age=settings.session_lifetime_seconds,
                httponly=settings.session_cookie_httponly,
                samesite=settings.session_cookie_samesite,
                secure=settings.session_cookie_secure,
                path=settings.session_cookie_path,
                domain=None,
            )

        return response

    except Exception as e:
        logger.error(f"Failed to proxy request: {e}")
        raise HTTPException(status_code=502, detail="Bad Gateway")


@app.get("/health")
async def health():
    """Health check эндпоинт."""
    return {"status": "healthy"}


# Проксирование фронтенда - должно быть последним, чтобы не перехватывать другие эндпоинты
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_frontend(request: Request, path: str):
    """
    Проксирование всех запросов к фронтенду (Vite dev server).
    Это позволяет фронтенду и API быть на одном домене (localhost:3000).
    """
    # Пропускаем API эндпоинты auth_proxy (они должны обрабатываться выше)
    # Если мы здесь и path - это API эндпоинт, значит что-то пошло не так
    api_endpoints = ["user_info", "sign_in", "callback", "sign_out", "proxy", "health"]
    if path in api_endpoints:
        # Этот запрос должен был быть обработан выше
        logger.error(f"API endpoint /{path} reached proxy_frontend - this should not happen!")
        raise HTTPException(status_code=500, detail=f"Internal routing error for /{path}")

    # Формируем URL для проксирования
    frontend_url = f"{settings.frontend_url}/{path}"

    # Копируем query параметры
    if request.url.query:
        frontend_url = f"{frontend_url}?{request.url.query}"

    # Копируем заголовки (кроме Host)
    headers = dict(request.headers)
    headers.pop("host", None)

    try:
        async with httpx.AsyncClient() as client:
            # Проксируем запрос
            if request.method == "GET":
                response = await client.get(frontend_url, headers=headers, follow_redirects=False)
            elif request.method == "POST":
                body = await request.body()
                response = await client.post(frontend_url, headers=headers, content=body, follow_redirects=False)
            elif request.method == "PUT":
                body = await request.body()
                response = await client.put(frontend_url, headers=headers, content=body, follow_redirects=False)
            elif request.method == "DELETE":
                response = await client.delete(frontend_url, headers=headers, follow_redirects=False)
            elif request.method == "PATCH":
                body = await request.body()
                response = await client.patch(frontend_url, headers=headers, content=body, follow_redirects=False)
            elif request.method == "HEAD":
                response = await client.head(frontend_url, headers=headers, follow_redirects=False)
            elif request.method == "OPTIONS":
                response = await client.options(frontend_url, headers=headers, follow_redirects=False)
            else:
                raise HTTPException(status_code=405, detail="Method Not Allowed")

        # Копируем заголовки ответа (кроме некоторых)
        excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
        response_headers = {
            key: value for key, value in response.headers.items() if key.lower() not in excluded_headers
        }

        # Возвращаем ответ
        return Response(content=response.content, status_code=response.status_code, headers=response_headers)

    except httpx.ConnectError:
        logger.error(f"Failed to connect to frontend at {frontend_url}")
        raise HTTPException(status_code=502, detail="Frontend unavailable")
    except Exception as e:
        logger.error(f"Failed to proxy frontend request: {e}")
        raise HTTPException(status_code=502, detail="Bad Gateway")
