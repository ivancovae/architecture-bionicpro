# BionicPro Frontend - Keycloak Integration

React приложение с интеграцией Keycloak OAuth 2.0 (PKCE).

## Технологии

- **React 18** - UI библиотека
- **TypeScript** - типизация
- **Vite** - сборщик и dev сервер
- **TailwindCSS** - стилизация
- **keycloak-js** v21.1.0 - официальная библиотека Keycloak
- **@react-keycloak/web** v3.4.0 - React интеграция для Keycloak

Приложение будет доступно по адресу: http://localhost:5173

## Конфигурация Keycloak

Конфигурация находится в `src/main.tsx`:

```typescript
const keycloakConfig = {
  url: 'http://localhost:8080',      // URL Keycloak сервера
  realm: 'reports-realm',             // Realm name
  clientId: 'reports-frontend'        // Client ID
}

const initOptions = {
  onLoad: 'check-sso',                // Проверка SSO без автоматического редиректа
  pkceMethod: 'S256'                  // Явное указание PKCE с SHA-256
}
```

## Особенности реализации

### PKCE (Proof Key for Code Exchange)
- **Явно указан** в двух местах:
  1. В `main.tsx` при инициализации: `pkceMethod: 'S256'`
  2. В `App.tsx` при вызове login: `keycloak.login({ pkceMethod: 'S256' })`
- Библиотека `keycloak-js` автоматически генерирует `code_verifier` и `code_challenge`
- Использует метод SHA-256 для хеширования

### Авторизация
1. Пользователь нажимает "Войти через Keycloak"
2. Перенаправляется на страницу входа Keycloak
3. После успешного входа возвращается обратно с authorization code
4. Библиотека автоматически обменивает code на токены (используя PKCE)
5. Токены сохраняются и доступны через `keycloak.token`

### Отображение информации
- **JWT токен декодируется** и отображается на странице
- Показываются основные поля: username, email, роли, время истечения
- Полный JSON payload доступен в раскрывающемся блоке

### Вызов Backend API
- Кнопка "Вызвать GET /reports" отправляет запрос на `http://localhost:3003/reports`
- JWT токен передается в заголовке `Authorization: Bearer <token>`
- Отображается HTTP статус код и JSON ответ от сервера

### Keycloak не редиректит обратно
- Проверьте, что в Keycloak настроены redirect URIs: `http://localhost:5173/*`
- Убедитесь, что Keycloak запущен на порту 8080

### CORS ошибки при вызове backend
- Убедитесь, что backend запущен с CORS middleware
- Проверьте, что `http://localhost:5173` добавлен в `allow_origins`
