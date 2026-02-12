import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'

// Получаем корневой элемент DOM
const container = document.getElementById('root')!

// Создаем корневой React элемент и рендерим приложение
createRoot(container).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
