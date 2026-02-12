import { useEffect, useState, useRef } from 'react'

// URL auth_proxy сервиса (теперь используем относительный путь, так как фронтенд работает через auth_proxy)
const AUTH_PROXY_URL = ''  // Пустая строка означает текущий домен (localhost:3002)

// Интерфейс для информации о пользователе
interface UserInfo {
  has_session_cookie: boolean
  is_authorized: boolean
  username?: string
  email?: string
  first_name?: string
  last_name?: string
  realm_roles?: string[]
  permissions?: any
  sub?: string
  external_uuid?: string  // UUID из LDAP (для LDAP-пользователей)
}

// Интерфейс для ответа от reports_api/jwt
interface JwtResponse {
  jwt: any | null
  error?: string
}

// Интерфейс для ответа от reports_api/reports
interface ReportResponse {
  user_name: string
  user_email: string
  total_events: number
  total_duration: number
  prosthesis_stats: Array<{
    prosthesis_type: string
    events_count: number
    total_duration: number
    avg_amplitude: number
    avg_frequency: number
  }>
  error?: string
  from_cache?: boolean  // Признак, что отчёт взят из кэша (устанавливается на фронтенде)
}

export default function App() {
  // Состояние: информация о пользователе
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null)
  
  // Состояние: загружается ли информация о пользователе
  const [loadingUserInfo, setLoadingUserInfo] = useState(true)
  
  // Состояние: сообщение об ошибке безопасности (409)
  const [securityError, setSecurityError] = useState<string | null>(null)
  
  // Состояние: ответ от reports_api/jwt
  const [jwtResponse, setJwtResponse] = useState<JwtResponse | null>(null)
  
  // Состояние: загружается ли запрос к reports_api/jwt
  const [loadingJwt, setLoadingJwt] = useState(false)
  
  // Состояние: ответ от reports_api/reports
  const [reportResponse, setReportResponse] = useState<ReportResponse | null>(null)
  
  // Состояние: загружается ли запрос к reports_api/reports
  const [loadingReport, setLoadingReport] = useState(false)
  
  // Состояние: происходит ли редирект
  const [isRedirecting, setIsRedirecting] = useState(false)
  
  // Состояние: какая секция активна ('jwt' | 'report-default' | 'report-debezium' | null)
  const [activeSection, setActiveSection] = useState<'jwt' | 'report-default' | 'report-debezium' | null>(null)
  
  // Состояние: загружается ли генерация данных
  const [loadingPopulate, setLoadingPopulate] = useState(false)
  
  // Состояние: результат генерации данных
  const [populateResult, setPopulateResult] = useState<string | null>(null)
  
  // Состояние: загружается ли запуск ETL (больше не используется, но оставляем для совместимости)
  const [loadingEtl, setLoadingEtl] = useState(false)
  
  // Состояние: результат запуска ETL
  const [etlResult, setEtlResult] = useState<string | null>(null)

  // Состояние: кастомный user_uuid для отчётов
  const [customUserUuid, setCustomUserUuid] = useState<string>('')

  // Refs для блоков результатов
  const jwtBlockRef = useRef<HTMLDivElement>(null)
  const reportBlockRef = useRef<HTMLDivElement>(null)

  // Загрузка информации о пользователе при монтировании компонента
  useEffect(() => {
    // Проверяем, не вернулись ли мы с callback
    const urlParams = new URLSearchParams(window.location.search)
    const hasError = urlParams.has('error')
    
    if (hasError) {
      console.error('Auth error:', urlParams.get('error'))
      setLoadingUserInfo(false)
      return
    }
    
    fetchUserInfo()
  }, [])

  // Автоматическая прокрутка к открывшемуся блоку
  useEffect(() => {
    if (activeSection === 'jwt' && jwtBlockRef.current) {
      // Небольшая задержка для завершения рендеринга
      setTimeout(() => {
        jwtBlockRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
      }, 100)
    } else if ((activeSection === 'report-default' || activeSection === 'report-debezium') && reportBlockRef.current) {
      setTimeout(() => {
        reportBlockRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
      }, 100)
    }
  }, [activeSection, jwtResponse, reportResponse])

  // Функция для получения информации о пользователе
  const fetchUserInfo = async () => {
    // Если уже происходит редирект, не делаем запрос
    if (isRedirecting) {
      return
    }
    
    setLoadingUserInfo(true)
    
    try {
      const response = await fetch(`${AUTH_PROXY_URL}/user_info`, {
        method: 'GET',
        credentials: 'include', // Включаем отправку cookies
      })
      
      if (response.ok) {
        const data: UserInfo = await response.json()
        setUserInfo(data)
        
        // Если пользователь не авторизован, редиректим на страницу входа
        if (!data.is_authorized) {
          // Устанавливаем флаг редиректа
          setIsRedirecting(true)
          console.log('User not authorized, redirecting to sign_in...')
          
          // Очищаем query параметры перед редиректом
          const cleanUrl = window.location.origin + window.location.pathname
          window.location.href = `${AUTH_PROXY_URL}/sign_in?redirect_to=${encodeURIComponent(cleanUrl)}`
          return // Прерываем выполнение
        }
        
        // Пользователь авторизован
        setLoadingUserInfo(false)
      } else if (response.status === 409) {
        // Обработка ошибки безопасности (невалидный session_id)
        const errorData = await response.json()
        const errorMessage = errorData.detail || 'Session ID невалидна. Возможна утечка или перехват сессии.'
        setSecurityError(errorMessage)
        console.error('Security error (409) in /user_info:', errorMessage)
        setLoadingUserInfo(false)
        return
      } else {
        console.error('Failed to fetch user info:', response.statusText)
        setLoadingUserInfo(false)
      }
    } catch (error) {
      console.error('Error fetching user info:', error)
      setLoadingUserInfo(false)
    }
  }

  // Функция для выхода из системы
  const handleSignOut = async () => {
    try {
      const response = await fetch(`${AUTH_PROXY_URL}/sign_out`, {
        method: 'POST',
        credentials: 'include',
      })
      
      console.log('Sign out response:', response.status)
      
      // Редиректим на /sign_in (это перенаправит на Keycloak)
      // Используем window.location.replace для принудительного редиректа
      window.location.replace(`/sign_in?redirect_to=${encodeURIComponent(window.location.origin)}`)
    } catch (error) {
      console.error('Error signing out:', error)
      // Все равно редиректим
      window.location.replace(`/sign_in?redirect_to=${encodeURIComponent(window.location.origin)}`)
    }
  }

  // Функция для получения JWT от reports_api через auth_proxy
  const fetchReportsJwt = async () => {
    setLoadingJwt(true)
    setJwtResponse(null)
    setReportResponse(null) // Скрываем отчёты
    setActiveSection('jwt') // Устанавливаем активную секцию
    
    try {
      // Проксируем запрос через auth_proxy (GET с query параметрами)
      // Используем имя сервиса Docker вместо localhost, так как auth_proxy работает внутри Docker
      const upstream_uri = encodeURIComponent('http://reports-api:3003/jwt')
      const response = await fetch(`${AUTH_PROXY_URL}/proxy?upstream_uri=${upstream_uri}&redirect_to_sign_in=false`, {
        method: 'GET',
        credentials: 'include',
      })
      
      if (response.ok) {
        const data: JwtResponse = await response.json()
        setJwtResponse(data)
      } else if (response.status === 409) {
        // Обработка ошибки безопасности (невалидный session_id)
        const errorData = await response.json()
        const errorMessage = errorData.detail || 'Session ID невалидна. Возможна утечка или перехват сессии.'
        setSecurityError(errorMessage)
        console.error('Security error (409):', errorMessage)
      } else {
        console.error('Failed to fetch JWT:', response.statusText)
        setJwtResponse({ jwt: null, error: `HTTP ${response.status}: ${response.statusText}` })
      }
    } catch (error) {
      console.error('Error fetching JWT:', error)
      setJwtResponse({ jwt: null, error: String(error) })
    } finally {
      setLoadingJwt(false)
    }
  }

  // Функция для генерации юзеров и событий
  const handlePopulateBase = async () => {
    setLoadingPopulate(true)
    setPopulateResult(null)
    
    try {
      // Вызываем /populate_base у crm_api
      const crmResponse = await fetch(`http://localhost:3001/populate_base`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      
      if (!crmResponse.ok) {
        throw new Error(`CRM API error: ${crmResponse.status} ${crmResponse.statusText}`)
      }
      
      const crmData = await crmResponse.json()
      console.log('CRM populate result:', crmData)
      
      // Вызываем /populate_base у telemetry_api
      const telemetryResponse = await fetch(`http://localhost:3002/populate_base`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      
      if (!telemetryResponse.ok) {
        throw new Error(`Telemetry API error: ${telemetryResponse.status} ${telemetryResponse.statusText}`)
      }
      
      const telemetryData = await telemetryResponse.json()
      console.log('Telemetry populate result:', telemetryData)
      
      setPopulateResult(`✓ Успешно сгенерировано:\n- Пользователей: ${crmData.users_loaded || 0}\n- Событий: ${telemetryData.events_loaded || 0}`)
    } catch (error) {
      console.error('Error populating base:', error)
      setPopulateResult(`✗ Ошибка: ${String(error)}`)
    } finally {
      setLoadingPopulate(false)
    }
  }
  
  // Функция для открытия ETL-процесса в Airflow UI
  const handleOpenEtlInAirflow = () => {
    // Открываем конкретную страницу DAG в Airflow UI
    const dagId = 'import_olap_data_monthly'
    const taskId = 'import_previous_month_data'
    const airflowUrl = `http://localhost:8082/dags/${dagId}/tasks/${taskId}`
    
    // Открываем в новой вкладке
    window.open(airflowUrl, '_blank')
    
    // Показываем сообщение пользователю
    setEtlResult('✓ Открыт Airflow UI. Вы можете запустить ETL-процесс вручную, нажав кнопку "Trigger DAG" или "Run".')
  }

  // Функция для формирования имени файла отчёта в MinIO
  const buildReportFileName = (
    schema: 'default' | 'debezium',
    user_uuid: string,
    start_ts: string | null,
    end_ts: string | null
  ): string => {
    // Форматируем имя файла так же, как в reports_api
    const formatTimestamp = (ts: string): string => {
      return ts.replace(/:/g, '-').replace(/\..+$/, '')
    }

    const userFolder = `${schema}/${user_uuid}`
    
    if (start_ts && end_ts) {
      const startStr = formatTimestamp(start_ts)
      const endStr = formatTimestamp(end_ts)
      return `${userFolder}/${startStr}__${endStr}.json`
    } else if (start_ts) {
      const startStr = formatTimestamp(start_ts)
      return `${userFolder}/${startStr}__none.json`
    } else if (end_ts) {
      const endStr = formatTimestamp(end_ts)
      return `${userFolder}/none__${endStr}.json`
    } else {
      return `${userFolder}/all_time.json`
    }
  }

  // Функция для создания отчёта
  const generateReport = async (schema: 'default' | 'debezium') => {
    setLoadingReport(true)
    setReportResponse(null)
    setJwtResponse(null) // Скрываем JWT
    setActiveSection(schema === 'default' ? 'report-default' : 'report-debezium') // Устанавливаем активную секцию
    
    try {
      // Вычисляем end_ts: 00:00 и 1 число текущего месяца по UTC
      const now = new Date()
      const firstDayOfMonth = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1, 0, 0, 0, 0))
      const end_ts = firstDayOfMonth.toISOString()
      
      // Определяем user_uuid для отчёта
      // Приоритет: customUserUuid > external_uuid (LDAP) > sub (локальные пользователи)
      const targetUserUuid = customUserUuid.trim() || userInfo.external_uuid || userInfo.sub || ''
      
      if (!targetUserUuid) {
        throw new Error('Не удалось определить UUID пользователя')
      }
      
      // Формируем имя файла в MinIO
      const fileName = buildReportFileName(schema, targetUserUuid, null, end_ts)
      
      // Сначала проверяем, есть ли отчёт в MinIO через nginx_minio_proxy
      // URL формата: http://minio-nginx:9001/reports/{schema}/{user_uuid}/{filename}
      const minioUrl = `http://minio-nginx:9001/reports/${fileName}`
      const minioProxyRequestBody = {
        upstream_uri: minioUrl,
        method: 'GET',
        redirect_to_sign_in: false
      }
      
      // Пробуем скачать отчёт из MinIO через auth-proxy → nginx_minio_proxy
      const minioResponse = await fetch(`${AUTH_PROXY_URL}/proxy`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(minioProxyRequestBody)
      })
      
      if (minioResponse.ok) {
        // Отчёт найден в кэше
        const cachedReport: ReportResponse = await minioResponse.json()
        cachedReport.from_cache = true
        setReportResponse(cachedReport)
        console.log('✓ Отчёт загружен из MinIO кэша:', fileName)
        return
      } else if (minioResponse.status === 409) {
        // Обработка ошибки безопасности (невалидный session_id)
        const errorData = await minioResponse.json()
        const errorMessage = errorData.detail || 'Session ID невалидна. Возможна утечка или перехват сессии.'
        setSecurityError(errorMessage)
        console.error('Security error (409):', errorMessage)
        return
      }
      
      // Отчёт не найден в кэше (или нет доступа), генерируем новый
      console.log('Отчёт не найден в кэше, генерируем новый...')
      
      // Формируем тело запроса для reports_api
      const reportsRequestBody = {
        start_ts: null,
        end_ts: end_ts,
        schema: schema,
        // Добавляем кастомный user_uuid, если он указан
        ...(customUserUuid.trim() && { user_uuid: customUserUuid.trim() })
      }
      
      // Формируем тело запроса для auth_proxy
      // Используем имя сервиса Docker вместо localhost, так как auth_proxy работает внутри Docker
      const proxyRequestBody = {
        upstream_uri: 'http://reports-api:3003/reports',
        method: 'POST',
        redirect_to_sign_in: false,
        body: reportsRequestBody
      }
      
      // Проксируем запрос через auth_proxy
      const response = await fetch(`${AUTH_PROXY_URL}/proxy`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(proxyRequestBody)
      })
      
      if (response.ok) {
        const data: ReportResponse = await response.json()
        data.from_cache = false  // Отчёт сгенерирован заново
        setReportResponse(data)
      } else if (response.status === 409) {
        // Обработка ошибки безопасности (невалидный session_id)
        const errorData = await response.json()
        const errorMessage = errorData.detail || 'Session ID невалидна. Возможна утечка или перехват сессии.'
        setSecurityError(errorMessage)
        console.error('Security error (409):', errorMessage)
      } else {
        const errorText = await response.text()
        console.error('Failed to generate report:', response.statusText, errorText)
        setReportResponse({ 
          user_name: '',
          user_email: '',
          total_events: 0,
          total_duration: 0,
          prosthesis_stats: [],
          error: `HTTP ${response.status}: ${errorText}` 
        })
      }
    } catch (error) {
      console.error('Error generating report:', error)
      setReportResponse({ 
        user_name: '',
        user_email: '',
        total_events: 0,
        total_duration: 0,
        prosthesis_stats: [],
        error: String(error) 
      })
    } finally {
      setLoadingReport(false)
    }
  }

  // Показываем индикатор загрузки, пока проверяем авторизацию
  if (loadingUserInfo) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-xl">Загрузка...</div>
      </div>
    )
  }

  // Если пользователь не авторизован, показываем сообщение (редирект произойдет автоматически)
  if (!userInfo || !userInfo.is_authorized) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        {/* Поп-ап с ошибкой безопасности (показываем даже если не авторизован) */}
        {securityError && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md mx-4">
              <h2 className="text-2xl font-bold text-red-600 mb-4">⚠️ Ошибка безопасности</h2>
              <p className="text-gray-700 mb-6 whitespace-pre-wrap">{securityError}</p>
              <div className="flex gap-4">
                <button
                  onClick={() => {
                    setSecurityError(null)
                    window.location.href = '/sign_out'
                  }}
                  className="flex-1 bg-red-600 text-white py-2 px-4 rounded-lg hover:bg-red-700 transition"
                >
                  Выйти
                </button>
                <button
                  onClick={() => setSecurityError(null)}
                  className="flex-1 bg-gray-300 text-gray-700 py-2 px-4 rounded-lg hover:bg-gray-400 transition"
                >
                  Закрыть
                </button>
              </div>
            </div>
          </div>
        )}
        <div className="text-xl">Перенаправление на страницу входа...</div>
      </div>
    )
  }

  // Пользователь авторизован - показываем главную страницу
  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 space-y-6">
        {/* Поп-ап с ошибкой безопасности */}
        {securityError && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md mx-4">
              <h2 className="text-2xl font-bold text-red-600 mb-4">⚠️ Ошибка безопасности</h2>
              <p className="text-gray-700 mb-6 whitespace-pre-wrap">{securityError}</p>
              <div className="flex gap-4">
                <button
                  onClick={() => {
                    setSecurityError(null)
                    window.location.href = '/sign_out'
                  }}
                  className="flex-1 bg-red-600 text-white py-2 px-4 rounded-lg hover:bg-red-700 transition"
                >
                  Выйти
                </button>
                <button
                  onClick={() => setSecurityError(null)}
                  className="flex-1 bg-gray-300 text-gray-700 py-2 px-4 rounded-lg hover:bg-gray-400 transition"
                >
                  Закрыть
                </button>
              </div>
            </div>
          </div>
        )}
        
        {/* Заголовок и кнопка выхода */}
        <div className="bg-white rounded-2xl shadow p-6">
          <div className="flex justify-between items-center">
            <h1 className="text-3xl font-bold text-green-600">
              ✓ Вы авторизованы!
            </h1>
            <button
              onClick={handleSignOut}
              className="bg-red-600 text-white py-2 px-4 rounded-lg hover:bg-red-700 transition"
            >
              Выйти
            </button>
          </div>
        </div>

        {/* Блок с информацией о пользователе */}
        <div className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-xl font-bold mb-4">Информация о пользователе</h2>
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="font-semibold">Пользователь:</div>
              <div>{userInfo.username || 'N/A'}</div>
              
              <div className="font-semibold">Email:</div>
              <div>{userInfo.email || 'N/A'}</div>
              
              <div className="font-semibold">Имя:</div>
              <div>{userInfo.first_name || 'N/A'}</div>
              
              <div className="font-semibold">Фамилия:</div>
              <div>{userInfo.last_name || 'N/A'}</div>
              
              <div className="font-semibold">Subject (ID):</div>
              <div className="break-all">{userInfo.sub || 'N/A'}</div>
              
              <div className="font-semibold">Роли:</div>
              <div>{userInfo.realm_roles?.join(', ') || 'N/A'}</div>
            </div>
            
            {/* Полный JSON user_info */}
            <details className="mt-4">
              <summary className="cursor-pointer font-semibold text-blue-600 hover:text-blue-800">
                Показать полный user_info (JSON)
              </summary>
              <pre className="mt-2 p-4 bg-gray-100 rounded-lg overflow-auto text-xs">
                {JSON.stringify(userInfo, null, 2)}
              </pre>
            </details>
          </div>
        </div>

        {/* Блок для ETL-операций */}
        <div className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-xl font-bold mb-4">ETL-операции</h2>
          
          {/* Кнопки для ETL */}
          <div className="flex flex-wrap gap-3 mb-4">
            <button
              onClick={handlePopulateBase}
              disabled={loadingPopulate}
              className="bg-indigo-600 text-white py-2 px-6 rounded-lg hover:bg-indigo-700 transition disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {loadingPopulate ? 'Генерация...' : 'Сгенерировать юзеров и события'}
            </button>
            
            <button
              onClick={handleOpenEtlInAirflow}
              className="bg-orange-600 text-white py-2 px-6 rounded-lg hover:bg-orange-700 transition"
            >
              Открыть ETL-процесс в Airflow
            </button>
          </div>
          
          {/* Результат генерации данных */}
          {populateResult && (
            <div className="mt-4 p-4 bg-gray-100 rounded-lg">
              <pre className="text-sm whitespace-pre-wrap">{populateResult}</pre>
            </div>
          )}
          
          {/* Результат запуска ETL */}
          {etlResult && (
            <div className="mt-4 p-4 bg-gray-100 rounded-lg">
              <pre className="text-sm whitespace-pre-wrap">{etlResult}</pre>
            </div>
          )}
          
          {/* Форма для кастомного user_uuid */}
          <div className="mt-6 p-4 border-t border-gray-200">
            <h3 className="text-lg font-semibold mb-3">Настройки отчётов</h3>
            <div className="flex flex-col gap-2">
              <label htmlFor="customUserUuid" className="text-sm font-medium text-gray-700">
                Кастомный User UUID (оставьте пустым для использования вашего UUID):
              </label>
              <input
                id="customUserUuid"
                type="text"
                value={customUserUuid}
                onChange={(e) => setCustomUserUuid(e.target.value)}
                placeholder="Введите UUID пользователя (например: 54885c9b-6eea-48f7-89f9-353ad8273e95)"
                className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
              />
              <p className="text-xs text-gray-500">
                Администраторы могут просматривать отчёты любых пользователей. 
                Обычные пользователи могут просматривать только свои отчёты.
              </p>
            </div>
          </div>
        </div>

        {/* Блок для вызова reports_api/jwt */}
        <div className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-xl font-bold mb-4">Запросы к reports_api</h2>
          
          {/* Кнопки для вызова различных эндпоинтов */}
          <div className="flex flex-wrap gap-3 mb-4">
            <button
              onClick={fetchReportsJwt}
              disabled={loadingJwt}
              className="bg-blue-600 text-white py-2 px-6 rounded-lg hover:bg-blue-700 transition disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {loadingJwt ? 'Загрузка...' : 'Посмотреть JWT'}
            </button>
            
            <button
              onClick={() => generateReport('default')}
              disabled={loadingReport}
              className="bg-green-600 text-white py-2 px-6 rounded-lg hover:bg-green-700 transition disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {loadingReport ? 'Загрузка...' : 'Отчёт (default)'}
            </button>
            
            <button
              onClick={() => generateReport('debezium')}
              disabled={loadingReport}
              className="bg-purple-600 text-white py-2 px-6 rounded-lg hover:bg-purple-700 transition disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {loadingReport ? 'Загрузка...' : 'Отчёт (debezium)'}
            </button>
          </div>

          {/* Отображение результата запроса JWT */}
          {jwtResponse && activeSection === 'jwt' && (
            <div ref={jwtBlockRef} className="mt-4 max-h-[800px] overflow-y-auto border border-gray-200 rounded-lg">
              {jwtResponse.jwt ? (
                <div className="p-4">
                  <div className="font-semibold mb-2 text-green-600">✓ JWT получен от reports_api:</div>
                  <pre className="p-4 bg-gray-100 rounded-lg overflow-auto text-sm">
                    {JSON.stringify(jwtResponse.jwt, null, 2)}
                  </pre>
                </div>
              ) : (
                <div className="p-4">
                  <div className="font-semibold mb-2 text-orange-600">⚠ JWT не найден</div>
                  {jwtResponse.error && (
                    <pre className="p-4 bg-orange-50 rounded-lg overflow-auto text-sm text-orange-800">
                      {jwtResponse.error}
                    </pre>
                  )}
                </div>
              )}
            </div>
          )}
          
          {/* Отображение результата запроса отчёта */}
          {reportResponse && (activeSection === 'report-default' || activeSection === 'report-debezium') && (
            <div ref={reportBlockRef} className="mt-4 max-h-[800px] overflow-y-auto border border-gray-200 rounded-lg">
              {reportResponse.error ? (
                <div className="p-4">
                  <div className="font-semibold mb-2 text-red-600">✗ Ошибка при создании отчёта</div>
                  <pre className="p-4 bg-red-50 rounded-lg overflow-auto text-sm text-red-800">
                    {reportResponse.error}
                  </pre>
                </div>
              ) : (
                <div className="p-4">
                  <div className="font-semibold mb-2 text-green-600">✓ Отчёт создан успешно:</div>
                  <div className="p-4 bg-gray-100 rounded-lg">
                    <div className="grid grid-cols-2 gap-2 text-sm mb-4">
                      {/* Признак кэша */}
                      <div className="font-semibold">Источник:</div>
                      <div>
                        {reportResponse.from_cache ? (
                          <span className="text-blue-600 font-semibold">📦 Из кэша</span>
                        ) : (
                          <span className="text-green-600 font-semibold">🔄 Не из кэша</span>
                        )}
                      </div>
                      
                      <div className="font-semibold">Пользователь:</div>
                      <div>{reportResponse.user_name}</div>
                      
                      <div className="font-semibold">Email:</div>
                      <div>{reportResponse.user_email}</div>
                      
                      <div className="font-semibold">Всего событий:</div>
                      <div>{reportResponse.total_events}</div>
                      
                      <div className="font-semibold">Общая длительность:</div>
                      <div>{reportResponse.total_duration} мс</div>
                    </div>
                    
                    {reportResponse.prosthesis_stats.length > 0 && (
                      <div>
                        <div className="font-semibold mb-2">Статистика по протезам:</div>
                        <div className="space-y-2">
                          {reportResponse.prosthesis_stats.map((stat, idx) => (
                            <div key={idx} className="bg-white p-3 rounded border">
                              <div className="font-semibold">{stat.prosthesis_type}</div>
                              <div className="text-xs text-gray-600 mt-1">
                                События: {stat.events_count} | 
                                Длительность: {stat.total_duration} мс | 
                                Ср. амплитуда: {stat.avg_amplitude.toFixed(2)} | 
                                Ср. частота: {stat.avg_frequency.toFixed(2)} Гц
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    <details className="mt-4">
                      <summary className="cursor-pointer font-semibold text-blue-600 hover:text-blue-800">
                        Показать полный JSON
                      </summary>
                      <pre className="mt-2 p-4 bg-white rounded-lg overflow-auto text-xs">
                        {JSON.stringify(reportResponse, null, 2)}
                      </pre>
                    </details>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
