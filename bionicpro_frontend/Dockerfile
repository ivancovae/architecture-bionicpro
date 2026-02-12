# Используем официальный образ Node.js
FROM node:18-alpine

# Устанавливаем curl для healthcheck
RUN apk add --no-cache curl

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем package.json и package-lock.json для установки зависимостей
COPY package*.json ./

# Устанавливаем зависимости
RUN npm install

# Копируем весь код приложения
COPY . .

# Открываем порт для Vite dev server
EXPOSE 5173

# Запускаем dev server (для production используйте npm run build && npm run preview)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
