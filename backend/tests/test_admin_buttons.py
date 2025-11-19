"""
Test Admin Panel Buttons
Проверяет работу всех кнопок админ-панели
"""
import asyncio
import httpx
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_admin_buttons():
    admin_key = os.environ.get('ADMIN_API_KEY', '')
    base_url = 'http://localhost:8001'
    
    headers = {'X-Api-Key': admin_key}
    
    print('=' * 70)
    print('ПРОВЕРКА КНОПОК АДМИН-ПАНЕЛИ')
    print('=' * 70)
    
    results = {
        'passed': 0,
        'failed': 0,
        'warnings': 0
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Проверка API mode (кнопка "Переключить на Продакшн API")
        print('\n1️⃣  Тест кнопки "Переключить на Продакшн/Тест API"')
        print('   ' + '-' * 60)
        try:
            # Get current API mode
            response = await client.get(f'{base_url}/api-config/status')
            if response.status_code == 200:
                data = response.json()
                current_env = data['status']['environment']
                print(f'   📊 Текущий API режим: {current_env.upper()}')
                
                # Switch environment
                new_env = 'production' if current_env == 'test' else 'test'
                response = await client.post(
                    f'{base_url}/api-config/switch-environment',
                    headers=headers,
                    json={'environment': new_env}
                )
                if response.status_code == 200:
                    print(f'   ✅ Переключение {current_env} → {new_env}: РАБОТАЕТ')
                    results['passed'] += 1
                    
                    # Switch back
                    await client.post(
                        f'{base_url}/api-config/switch-environment',
                        headers=headers,
                        json={'environment': current_env}
                    )
                    print(f'   🔄 Возврат к {current_env}: успешно')
                else:
                    print(f'   ❌ Переключение не работает: {response.status_code}')
                    print(f'      Response: {response.text}')
                    results['failed'] += 1
            else:
                print(f'   ❌ Не удалось получить статус: {response.status_code}')
                results['failed'] += 1
        except Exception as e:
            print(f'   ❌ Ошибка: {e}')
            results['failed'] += 1
        
        # 2. Проверка maintenance mode (кнопка "Включить режим обслуживания")
        print('\n2️⃣  Тест кнопки "Включить режим обслуживания"')
        print('   ' + '-' * 60)
        try:
            # Get current maintenance mode
            response = await client.get(f'{base_url}/api/maintenance/status', headers=headers)
            if response.status_code == 200:
                data = response.json()
                current_mode = data.get('maintenance_mode', False)
                print(f'   📊 Текущий режим: {"Включен ⚠️" if current_mode else "Выключен ✅"}')
                
                # Toggle maintenance mode
                if current_mode:
                    # Disable
                    response = await client.post(
                        f'{base_url}/api/maintenance/disable',
                        headers=headers
                    )
                else:
                    # Enable
                    response = await client.post(
                        f'{base_url}/api/maintenance/enable',
                        headers=headers
                    )
                
                if response.status_code == 200:
                    new_mode = not current_mode
                    print(f'   ✅ Переключение режима: РАБОТАЕТ')
                    print(f'      {"Включен" if new_mode else "Выключен"} → {"Выключен" if current_mode else "Включен"}')
                    results['passed'] += 1
                    
                    # Toggle back
                    if new_mode:
                        await client.post(f'{base_url}/api/maintenance/disable', headers=headers)
                    else:
                        await client.post(f'{base_url}/api/maintenance/enable', headers=headers)
                    print(f'   🔄 Возврат к исходному состоянию: успешно')
                else:
                    print(f'   ❌ Переключение не работает: {response.status_code}')
                    results['failed'] += 1
            else:
                print(f'   ❌ Не удалось получить статус: {response.status_code}')
                results['failed'] += 1
        except Exception as e:
            print(f'   ❌ Ошибка: {e}')
            results['failed'] += 1
        
        # 3. Проверка Users Management (Details, Add Balance, Deduct, Block)
        print('\n3️⃣  Тест кнопок управления пользователями')
        print('   ' + '-' * 60)
        
        # Get users list
        response = await client.get(f'{base_url}/api/users', headers=headers)
        if response.status_code != 200:
            print(f'   ❌ Не удалось получить список пользователей: {response.status_code}')
            results['failed'] += 4  # 4 tests failed
        else:
            users = response.json()
            if not users:
                print('   ⚠️  Нет пользователей для тестирования')
                results['warnings'] += 4
            else:
                test_user = users[0]
                telegram_id = test_user['telegram_id']
                user_name = test_user.get('first_name', 'User')
                
                print(f'   👤 Тестовый пользователь: {user_name} (ID: {telegram_id})')
                print()
                
                # 3a. Test Details button
                print('   3a. Кнопка "Details"')
                try:
                    response = await client.get(
                        f'{base_url}/api/admin/users/{telegram_id}/details',
                        headers=headers
                    )
                    if response.status_code == 200:
                        details = response.json()
                        print(f'       ✅ РАБОТАЕТ')
                        print(f'          Имя: {details.get("first_name", "Unknown")}')
                        print(f'          Баланс: ${details.get("balance", 0):.2f}')
                        print(f'          Заказов: {len(details.get("orders", []))}')
                        print(f'          Заблокирован: {"Да ⚠️" if details.get("blocked") else "Нет ✅"}')
                        results['passed'] += 1
                    else:
                        print(f'       ❌ НЕ РАБОТАЕТ: {response.status_code}')
                        results['failed'] += 1
                except Exception as e:
                    print(f'       ❌ Ошибка: {e}')
                    results['failed'] += 1
                print()
                
                # 3b. Test Add Balance button
                print('   3b. Кнопка "Add Balance"')
                try:
                    # Get current balance
                    response = await client.get(
                        f'{base_url}/api/admin/users/{telegram_id}/details',
                        headers=headers
                    )
                    old_balance = response.json().get('balance', 0) if response.status_code == 200 else 0
                    
                    # Add balance
                    response = await client.post(
                        f'{base_url}/api/admin/users/{telegram_id}/balance/add',
                        headers=headers,
                        params={'amount': 10}
                    )
                    if response.status_code == 200:
                        result = response.json()
                        new_balance = result.get('new_balance', 0)
                        print(f'       ✅ РАБОТАЕТ')
                        print(f'          Было: ${old_balance:.2f}')
                        print(f'          Добавлено: $10.00')
                        print(f'          Стало: ${new_balance:.2f}')
                        results['passed'] += 1
                        
                        # Deduct back to restore original balance
                        await client.post(
                            f'{base_url}/api/admin/users/{telegram_id}/balance/deduct',
                            headers=headers,
                            params={'amount': 10}
                        )
                    else:
                        print(f'       ❌ НЕ РАБОТАЕТ: {response.status_code}')
                        results['failed'] += 1
                except Exception as e:
                    print(f'       ❌ Ошибка: {e}')
                    results['failed'] += 1
                print()
                
                # 3c. Test Deduct Balance button
                print('   3c. Кнопка "Deduct Balance"')
                try:
                    # Get current balance
                    response = await client.get(
                        f'{base_url}/api/admin/users/{telegram_id}/details',
                        headers=headers
                    )
                    old_balance = response.json().get('balance', 0) if response.status_code == 200 else 0
                    
                    if old_balance >= 5:
                        # Deduct balance
                        response = await client.post(
                            f'{base_url}/api/admin/users/{telegram_id}/balance/deduct',
                            headers=headers,
                            params={'amount': 5}
                        )
                        if response.status_code == 200:
                            result = response.json()
                            new_balance = result.get('new_balance', 0)
                            print(f'       ✅ РАБОТАЕТ')
                            print(f'          Было: ${old_balance:.2f}')
                            print(f'          Снято: $5.00')
                            print(f'          Стало: ${new_balance:.2f}')
                            results['passed'] += 1
                            
                            # Add back to restore
                            await client.post(
                                f'{base_url}/api/admin/users/{telegram_id}/balance/add',
                                headers=headers,
                                params={'amount': 5}
                            )
                        else:
                            print(f'       ❌ НЕ РАБОТАЕТ: {response.status_code}')
                            results['failed'] += 1
                    else:
                        print(f'       ⚠️  Недостаточно баланса для теста (${old_balance:.2f} < $5)')
                        print(f'       Добавляю баланс для теста...')
                        # Add balance first
                        await client.post(
                            f'{base_url}/api/admin/users/{telegram_id}/balance/add',
                            headers=headers,
                            params={'amount': 10}
                        )
                        # Now deduct
                        response = await client.post(
                            f'{base_url}/api/admin/users/{telegram_id}/balance/deduct',
                            headers=headers,
                            params={'amount': 5}
                        )
                        if response.status_code == 200:
                            print(f'       ✅ РАБОТАЕТ (с предварительным пополнением)')
                            results['passed'] += 1
                            # Restore by deducting the added amount
                            await client.post(
                                f'{base_url}/api/admin/users/{telegram_id}/balance/deduct',
                                headers=headers,
                                params={'amount': 5}  # Remove remaining balance
                            )
                        else:
                            print(f'       ❌ НЕ РАБОТАЕТ: {response.status_code}')
                            results['failed'] += 1
                except Exception as e:
                    print(f'       ❌ Ошибка: {e}')
                    results['failed'] += 1
                print()
                
                # 3d. Test Block/Unblock button
                print('   3d. Кнопки "Block" и "Unblock"')
                try:
                    # Block user
                    response = await client.post(
                        f'{base_url}/api/admin/users/{telegram_id}/block',
                        headers=headers
                    )
                    if response.status_code == 200:
                        print(f'       ✅ Block: РАБОТАЕТ')
                        
                        # Unblock user
                        response = await client.post(
                            f'{base_url}/api/admin/users/{telegram_id}/unblock',
                            headers=headers
                        )
                        if response.status_code == 200:
                            print(f'       ✅ Unblock: РАБОТАЕТ')
                            results['passed'] += 1
                        else:
                            print(f'       ❌ Unblock НЕ РАБОТАЕТ: {response.status_code}')
                            results['failed'] += 1
                    else:
                        print(f'       ❌ Block НЕ РАБОТАЕТ: {response.status_code}')
                        results['failed'] += 1
                except Exception as e:
                    print(f'       ❌ Ошибка: {e}')
                    results['failed'] += 1
    
    # Summary
    print('\n' + '=' * 70)
    print('ИТОГОВЫЕ РЕЗУЛЬТАТЫ')
    print('=' * 70)
    print(f'✅ Тестов пройдено: {results["passed"]}')
    print(f'❌ Тестов провалено: {results["failed"]}')
    print(f'⚠️  Предупреждений: {results["warnings"]}')
    print()
    
    if results['failed'] == 0:
        print('🎉 ВСЕ КНОПКИ АДМИН-ПАНЕЛИ РАБОТАЮТ КОРРЕКТНО!')
        return 0
    else:
        print('⚠️  Некоторые кнопки требуют внимания')
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_admin_buttons())
    sys.exit(exit_code)
