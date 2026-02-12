"""Примеры запросов к ClickHouse OLAP БД через clickhouse-connect."""

import clickhouse_connect
from datetime import datetime


def get_client():
    """Создает подключение к ClickHouse."""
    return clickhouse_connect.get_client(
        host='localhost',
        port=8123,
        username='default',
        password='clickhouse_password'
    )


def example_1_total_users():
    """Пример 1: Общее количество пользователей."""
    client = get_client()
    
    result = client.query("SELECT COUNT(*) FROM users")
    total_users = result.result_rows[0][0]
    
    print(f"Общее количество пользователей: {total_users}")
    return total_users


def example_2_total_events():
    """Пример 2: Общее количество телеметрических событий."""
    client = get_client()
    
    result = client.query("SELECT COUNT(*) FROM telemetry_events")
    total_events = result.result_rows[0][0]
    
    print(f"Общее количество событий: {total_events}")
    return total_events


def example_3_events_by_user(user_id: int):
    """Пример 3: Количество событий для конкретного пользователя."""
    client = get_client()
    
    query = """
    SELECT COUNT(*) 
    FROM telemetry_events 
    WHERE user_id = {user_id:Int32}
    """
    
    result = client.query(query, parameters={'user_id': user_id})
    events_count = result.result_rows[0][0]
    
    print(f"Количество событий для пользователя {user_id}: {events_count}")
    return events_count


def example_4_events_by_month():
    """Пример 4: Количество событий по месяцам."""
    client = get_client()
    
    query = """
    SELECT 
        toYear(event_timestamp) as year,
        toMonth(event_timestamp) as month,
        COUNT(*) as events_count
    FROM telemetry_events
    GROUP BY year, month
    ORDER BY year, month
    """
    
    result = client.query(query)
    
    print("\nКоличество событий по месяцам:")
    for year, month, count in result.result_rows:
        print(f"  {year}-{month:02d}: {count} событий")
    
    return result.result_rows


def example_5_avg_signal_by_prosthesis():
    """Пример 5: Средняя амплитуда и частота сигнала по типам протезов."""
    client = get_client()
    
    query = """
    SELECT 
        prosthesis_type,
        COUNT(*) as events_count,
        AVG(signal_amplitude) as avg_amplitude,
        AVG(signal_frequency) as avg_frequency,
        SUM(signal_duration) as total_duration
    FROM telemetry_events
    GROUP BY prosthesis_type
    ORDER BY events_count DESC
    """
    
    result = client.query(query)
    
    print("\nСтатистика по типам протезов:")
    for prosthesis, count, avg_amp, avg_freq, total_dur in result.result_rows:
        print(f"  {prosthesis}:")
        print(f"    События: {count}")
        print(f"    Средняя амплитуда: {avg_amp:.2f}")
        print(f"    Средняя частота: {avg_freq:.2f} Гц")
        print(f"    Общая длительность: {total_dur} мс")
    
    return result.result_rows


def example_6_user_report(user_id: int, start_date: datetime = None, end_date: datetime = None):
    """Пример 6: Детальный отчет по пользователю за период."""
    client = get_client()
    
    # Получаем информацию о пользователе
    user_query = """
    SELECT name, email, registration_ts
    FROM users
    WHERE user_id = {user_id:Int32}
    """
    
    user_result = client.query(user_query, parameters={'user_id': user_id})
    
    if not user_result.result_rows:
        print(f"Пользователь {user_id} не найден")
        return None
    
    name, email, registration_ts = user_result.result_rows[0]
    
    # Формируем запрос для событий с учетом временных фильтров
    events_query = """
    SELECT 
        COUNT(*) as total_events,
        SUM(signal_duration) as total_duration,
        AVG(signal_amplitude) as avg_amplitude,
        AVG(signal_frequency) as avg_frequency
    FROM telemetry_events
    WHERE user_id = {user_id:Int32}
    """
    
    params = {'user_id': user_id}
    
    if start_date:
        events_query += " AND event_timestamp >= {start_date:DateTime}"
        params['start_date'] = start_date
    
    if end_date:
        events_query += " AND event_timestamp < {end_date:DateTime}"
        params['end_date'] = end_date
    
    events_result = client.query(events_query, parameters=params)
    total_events, total_duration, avg_amplitude, avg_frequency = events_result.result_rows[0]
    
    # Статистика по протезам
    prosthesis_query = """
    SELECT 
        prosthesis_type,
        COUNT(*) as events_count,
        SUM(signal_duration) as total_duration,
        AVG(signal_amplitude) as avg_amplitude,
        AVG(signal_frequency) as avg_frequency
    FROM telemetry_events
    WHERE user_id = {user_id:Int32}
    """
    
    if start_date:
        prosthesis_query += " AND event_timestamp >= {start_date:DateTime}"
    
    if end_date:
        prosthesis_query += " AND event_timestamp < {end_date:DateTime}"
    
    prosthesis_query += " GROUP BY prosthesis_type ORDER BY events_count DESC"
    
    prosthesis_result = client.query(prosthesis_query, parameters=params)
    
    # Выводим отчет
    print(f"\n{'='*60}")
    print(f"ОТЧЕТ ПО ПОЛЬЗОВАТЕЛЮ")
    print(f"{'='*60}")
    print(f"Имя: {name}")
    print(f"Email: {email}")
    print(f"Дата регистрации: {registration_ts}")
    
    if start_date or end_date:
        print(f"\nОтчетный период:")
        if start_date:
            print(f"  С: {start_date}")
        if end_date:
            print(f"  По: {end_date}")
    
    print(f"\nОбщая статистика:")
    print(f"  Всего событий: {total_events}")
    print(f"  Общая длительность сигналов: {total_duration or 0} мс")
    
    if total_events > 0:
        print(f"  Средняя амплитуда: {avg_amplitude:.2f}")
        print(f"  Средняя частота: {avg_frequency:.2f} Гц")
    
    if prosthesis_result.result_rows:
        print(f"\nСтатистика по протезам:")
        for prosthesis, count, duration, amplitude, frequency in prosthesis_result.result_rows:
            print(f"  {prosthesis}:")
            print(f"    События: {count}")
            print(f"    Длительность: {duration} мс")
            print(f"    Средняя амплитуда: {amplitude:.2f}")
            print(f"    Средняя частота: {frequency:.2f} Гц")
    
    print(f"{'='*60}\n")
    
    return {
        'user': {'name': name, 'email': email, 'registration_ts': registration_ts},
        'total_events': total_events,
        'total_duration': total_duration,
        'avg_amplitude': avg_amplitude,
        'avg_frequency': avg_frequency,
        'prosthesis_stats': prosthesis_result.result_rows
    }


def example_7_top_active_users(limit: int = 10):
    """Пример 7: Топ самых активных пользователей."""
    client = get_client()
    
    query = """
    SELECT 
        te.user_id,
        u.name,
        u.email,
        COUNT(*) as events_count,
        SUM(te.signal_duration) as total_duration
    FROM telemetry_events te
    JOIN users u ON te.user_id = u.user_id
    GROUP BY te.user_id, u.name, u.email
    ORDER BY events_count DESC
    LIMIT {limit:Int32}
    """
    
    result = client.query(query, parameters={'limit': limit})
    
    print(f"\nТоп-{limit} самых активных пользователей:")
    for idx, (user_id, name, email, events, duration) in enumerate(result.result_rows, 1):
        print(f"  {idx}. {name} ({email})")
        print(f"     User ID: {user_id}")
        print(f"     События: {events}")
        print(f"     Общая длительность: {duration} мс")
    
    return result.result_rows


def example_8_events_by_muscle_group():
    """Пример 8: Распределение событий по группам мышц."""
    client = get_client()
    
    query = """
    SELECT 
        muscle_group,
        COUNT(*) as events_count,
        AVG(signal_amplitude) as avg_amplitude
    FROM telemetry_events
    GROUP BY muscle_group
    ORDER BY events_count DESC
    """
    
    result = client.query(query)
    
    print("\nРаспределение событий по группам мышц:")
    for muscle, count, avg_amp in result.result_rows:
        print(f"  {muscle}: {count} событий (средняя амплитуда: {avg_amp:.2f})")
    
    return result.result_rows


if __name__ == "__main__":
    print("Примеры запросов к ClickHouse OLAP БД")
    print("=" * 60)
    
    # Запускаем примеры
    example_1_total_users()
    example_2_total_events()
    example_4_events_by_month()
    example_5_avg_signal_by_prosthesis()
    
    # Пример отчета по пользователю (user_id=512, если есть в данных)
    example_6_user_report(
        user_id=512,
        start_date=datetime(2025, 3, 1),
        end_date=datetime(2025, 3, 31)
    )
    
    example_7_top_active_users(limit=5)
    example_8_events_by_muscle_group()
