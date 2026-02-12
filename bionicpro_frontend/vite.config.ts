import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'


export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        host: '0.0.0.0', // Слушаем на всех интерфейсах
        allowedHosts: [
            'bionicpro-frontend', // Имя сервиса в Docker Compose
            'auth-proxy', // auth_proxy может обращаться к фронтенду
            'localhost', // Локальный доступ
            '.localhost', // Поддомены localhost
        ],
        hmr: {
            // Отключаем HMR при проксировании через auth-proxy
            // так как auth-proxy не поддерживает WebSocket
            clientPort: 5173,
            host: 'localhost'
        }
    }
})