import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";

// Clean environment variables (Emergent platform concatenates them)
const cleanEnvValue = (value) => {
  if (!value) return value;
  return value.split('REACT_APP_')[0].split('MONGO_URL')[0].split('WEBHOOK_')[0].split('BOT_TOKEN')[0].trim();
};

const BACKEND_URL = cleanEnvValue(process.env.REACT_APP_BACKEND_URL) || "";
const ADMIN_API_KEY = cleanEnvValue(process.env.REACT_APP_ADMIN_API_KEY) || "";
const API = `${BACKEND_URL}/api`;

export default function MonitoringTab() {
  const [healthData, setHealthData] = useState(null);
  const [logs, setLogs] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [restarting, setRestarting] = useState(false);
  const [restartStatus, setRestartStatus] = useState("");

  const loadData = async () => {
    try {
      // Use correct monitoring endpoint
      const response = await axios.get(`${API}/monitoring/combined`, {
        headers: {
          'X-API-Key': ADMIN_API_KEY
        }
      });

      if (response.data.success) {
        setHealthData(response.data.health);
        setMetrics(response.data.application);
        
        // Logs are not available in this endpoint, keep them empty for now
        setLogs([]);
      }
    } catch (error) {
      console.error("Failed to load monitoring data", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    
    // Auto-refresh every 10 seconds
    const interval = setInterval(() => {
      if (autoRefresh) {
        loadData();
      }
    }, 10000);

    return () => clearInterval(interval);
  }, [autoRefresh]);

  const getLogColor = (level) => {
    switch (level) {
      case "ERROR":
        return "text-red-600 bg-red-50";
      case "WARNING":
        return "text-orange-600 bg-orange-50";
      default:
        return "text-gray-600 bg-gray-50";
    }
  };

  const getCategoryBadge = (category) => {
    const badges = {
      security: "🔒 Security",
      error: "❌ Error",
      warning: "⚠️ Warning",
      rate_limit: "⏱️ Rate Limit",
      blocked_user: "🚫 Blocked",
      api: "🔄 API",
      general: "📋 General"
    };
    return badges[category] || "📋 General";
  };

  const checkBotHealth = async () => {
    try {
      const response = await axios.get(`${API}/api/bot/health`, { 
        timeout: 3000
      });
      console.log("Health check response:", response.data.status);
      return response.data.status === "healthy";
    } catch (error) {
      console.log("Health check error:", error.message);
      return false;
    }
  };

  const waitForBotRestart = async () => {
    console.log("=== Starting bot restart sequence ===");
    setRestartStatus("⏳ Отправка команды перезагрузки...");
    
    // Wait 2 seconds for API response
    await new Promise(resolve => setTimeout(resolve, 2000));
    console.log("Initial wait complete, checking for shutdown...");
    
    // Step 1: Wait for bot to stop (check that it becomes unhealthy)
    setRestartStatus("🛑 Ожидание остановки бота...");
    let stopAttempts = 0;
    const maxStopAttempts = 5; // 5 * 2 seconds = 10 seconds max
    
    while (stopAttempts < maxStopAttempts) {
      console.log(`Stop check attempt ${stopAttempts + 1}/${maxStopAttempts}`);
      const isHealthy = await checkBotHealth();
      console.log(`Bot healthy during stop check: ${isHealthy}`);
      
      if (!isHealthy) {
        // Bot stopped!
        console.log("Bot successfully stopped!");
        setRestartStatus("✅ Бот остановлен, ожидание запуска...");
        await new Promise(resolve => setTimeout(resolve, 2000));
        break;
      }
      stopAttempts++;
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
    
    // Step 2: Wait for bot to start (check that it becomes healthy again)
    console.log("Starting health checks for bot startup...");
    let startAttempts = 0;
    const maxStartAttempts = 15; // 15 * 2 seconds = 30 seconds max
    
    while (startAttempts < maxStartAttempts) {
      setRestartStatus(`🔄 Ожидание запуска... (попытка ${startAttempts + 1}/${maxStartAttempts})`);
      console.log(`Start check attempt ${startAttempts + 1}/${maxStartAttempts}`);
      
      const isHealthy = await checkBotHealth();
      console.log(`Bot healthy during start check: ${isHealthy}`);
      
      if (isHealthy) {
        console.log("Bot is back online!");
        setRestartStatus("✅ Бот успешно перезагружен!");
        await new Promise(resolve => setTimeout(resolve, 1000));
        return true;
      }
      
      startAttempts++;
      await new Promise(resolve => setTimeout(resolve, 2000)); // Wait 2 seconds between attempts
    }
    
    console.log("Restart timeout exceeded");
    setRestartStatus("⚠️ Превышено время ожидания. Проверьте статус вручно.");
    return false;
  };

  const handleRestartBot = async () => {
    console.log("=== RESTART BUTTON CLICKED ===");
    
    if (!window.confirm("Вы уверены, что хотите перезагрузить бота? Это займёт 10-15 секунд.")) {
      console.log("User cancelled restart");
      return;
    }

    console.log("User confirmed restart");

    try {
      console.log("Setting restarting state...");
      setRestarting(true);
      setAutoRefresh(false); // Stop auto-refresh during restart
      
      console.log("Admin key:", ADMIN_API_KEY ? "present" : "missing");
      
      console.log("Sending restart request to API...");
      const response = await axios.post(`${API}/api/bot/restart`);
      console.log("Restart API response:", response.data);
      
      // Wait for bot to restart
      console.log("Starting waitForBotRestart...");
      const success = await waitForBotRestart();
      console.log("waitForBotRestart result:", success);
      
      if (success) {
        // Reload all data
        setRestartStatus("📊 Обновление данных...");
        await loadData();
        setRestartStatus("");
      }
      
    } catch (error) {
      console.error("ERROR in handleRestartBot:", error);
      setRestartStatus("❌ Ошибка: " + (error.response?.data?.detail || error.message));
      setTimeout(() => setRestartStatus(""), 5000);
    } finally {
      console.log("Cleaning up restart state...");
      setRestarting(false);
      setAutoRefresh(true); // Resume auto-refresh
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg text-gray-500">Загрузка мониторинга...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Restart Overlay */}
      {restarting && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-8 max-w-md w-full mx-4 shadow-xl">
            <div className="text-center">
              <div className="mb-4">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              </div>
              <h3 className="text-xl font-bold mb-2">Перезагрузка бота</h3>
              <p className="text-gray-600 mb-4">{restartStatus}</p>
              <div className="w-full bg-gray-200 rounded-full h-2.5">
                <div className="bg-blue-600 h-2.5 rounded-full animate-pulse" style={{width: '100%'}}></div>
              </div>
              <p className="text-sm text-gray-500 mt-4">
                Пожалуйста, не закрывайте эту страницу
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold">🛡️ Мониторинг и Безопасность</h2>
          <p className="text-sm text-gray-500">
            Real-time мониторинг здоровья и безопасности бота
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={handleRestartBot}
            variant="destructive"
            disabled={restarting || loading}
          >
            {restarting ? "⏳ Перезагрузка..." : "🔄 Перезагрузить бота"}
          </Button>
          <Button
            onClick={() => setAutoRefresh(!autoRefresh)}
            variant={autoRefresh ? "default" : "outline"}
            disabled={restarting}
          >
            {autoRefresh ? "🔄 Авто-обновление ON" : "⏸️ Авто-обновление OFF"}
          </Button>
          <Button onClick={loadData} variant="outline" disabled={restarting}>
            🔄 Обновить
          </Button>
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600">
              Статус бота
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-green-600">
              ✅ {healthData?.status}
            </div>
            <p className="text-xs text-gray-500 mt-2">
              {healthData?.protection?.instance_id}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600">
              Всего пользователей
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {healthData?.database_stats?.total_users || 0}
            </div>
            <p className="text-xs text-gray-500 mt-2">
              Заблокировано: {healthData?.database_stats?.blocked_users || 0}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600">
              Всего заказов
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {metrics?.orders?.total || 0}
            </div>
            <p className="text-xs text-gray-500 mt-2">
              Сегодня: {metrics?.orders?.today || 0}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-gray-600">
              API Mode
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {healthData?.api_config?.mode === "test" ? "🧪 Test" : "🚀 Prod"}
            </div>
            <p className="text-xs text-gray-500 mt-2">
              {healthData?.api_config?.mode}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Safety Statistics */}
      <Card>
        <CardHeader>
          <CardTitle>🛡️ Статистика безопасности</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-blue-50 rounded-lg">
              <div className="text-sm text-gray-600">Заблокированные</div>
              <div className="text-2xl font-bold text-blue-600">
                {healthData?.safety_statistics?.blocked_users_count || 0}
              </div>
            </div>
            <div className="p-4 bg-green-50 rounded-lg">
              <div className="text-sm text-gray-600">Активные диалоги</div>
              <div className="text-2xl font-bold text-green-600">
                {healthData?.safety_statistics?.active_conversations || 0}
              </div>
            </div>
            <div className="p-4 bg-purple-50 rounded-lg">
              <div className="text-sm text-gray-600">Сообщений/сек</div>
              <div className="text-2xl font-bold text-purple-600">
                {healthData?.safety_statistics?.global_messages_last_second || 0}
              </div>
            </div>
            <div className="p-4 bg-orange-50 rounded-lg">
              <div className="text-sm text-gray-600">Ошибки API</div>
              <div className="text-2xl font-bold text-orange-600">
                {Object.keys(healthData?.safety_statistics?.error_counts || {}).length}
              </div>
            </div>
          </div>

          {/* Protection Status */}
          <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg">
            <h3 className="font-semibold text-green-800 mb-2">
              ✅ Активные защиты
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
              {Object.entries(healthData?.protection || {}).map(([key, value]) => {
                if (typeof value === "string" && value === "active") {
                  return (
                    <div key={key} className="flex items-center gap-2 text-green-700">
                      <span>✓</span>
                      <span>{key.replace(/_/g, " ")}</span>
                    </div>
                  );
                }
                return null;
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Revenue Stats */}
      {metrics && (
        <Card>
          <CardHeader>
            <CardTitle>💰 Финансовая статистика</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 bg-green-50 rounded-lg">
                <div className="text-sm text-gray-600">Общая выручка</div>
                <div className="text-3xl font-bold text-green-600">
                  ${metrics?.revenue?.total?.toFixed(2) || '0.00'}
                </div>
              </div>
              <div className="p-4 bg-blue-50 rounded-lg">
                <div className="text-sm text-gray-600">Средний заказ</div>
                <div className="text-3xl font-bold text-blue-600">
                  ${metrics?.revenue?.average_order?.toFixed(2) || '0.00'}
                </div>
              </div>
              <div className="p-4 bg-purple-50 rounded-lg">
                <div className="text-sm text-gray-600">Активные пользователи</div>
                <div className="text-3xl font-bold text-purple-600">
                  {metrics?.users?.active_today || 0}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Logs */}
      <Card>
        <CardHeader>
          <CardTitle>📋 Логи системы (последние 50)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="max-h-96 overflow-y-auto space-y-2">
            {logs.length === 0 ? (
              <div className="text-center text-gray-500 py-8">
                Нет логов для отображения
              </div>
            ) : (
              logs.slice().reverse().map((log, index) => (
                <div
                  key={index}
                  className={`p-3 rounded-lg text-xs font-mono ${getLogColor(log.level)}`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold">{getCategoryBadge(log.category)}</span>
                    <span className="text-gray-500">{log.timestamp}</span>
                  </div>
                  <div className="whitespace-pre-wrap break-words">
                    {log.message}
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      {/* Best Practices */}
      <Card>
        <CardHeader>
          <CardTitle>✅ Best Practices ({healthData?.best_practices_active || 0})</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {healthData?.guidelines?.map((guideline, index) => (
              <li key={index} className="flex items-start gap-2 text-sm">
                <span className="text-green-600 mt-1">✓</span>
                <span>{guideline}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
