import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function MonitoringTab() {
  const [healthData, setHealthData] = useState(null);
  const [logs, setLogs] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadData = async () => {
    try {
      const [healthRes, logsRes, metricsRes] = await Promise.all([
        axios.get(`${API}/bot/health`),
        axios.get(`${API}/bot/logs?limit=50`),
        axios.get(`${API}/bot/metrics`)
      ]);

      setHealthData(healthRes.data);
      setLogs(logsRes.data.logs);
      setMetrics(metricsRes.data);
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

  const handleRestartBot = async () => {
    if (!window.confirm("Вы уверены, что хотите перезагрузить бота? Это займёт 5-10 секунд.")) {
      return;
    }

    try {
      setLoading(true);
      const adminKey = localStorage.getItem("adminKey");
      await axios.post(`${API}/api/bot/restart`, {}, {
        headers: { "X-Admin-Key": adminKey }
      });
      
      alert("✅ Бот перезагружается... Подождите 10 секунд и обновите страницу.");
      
      // Wait 10 seconds and reload data
      setTimeout(() => {
        loadData();
      }, 10000);
    } catch (error) {
      console.error("Failed to restart bot:", error);
      alert("❌ Ошибка при перезагрузке бота: " + (error.response?.data?.detail || error.message));
      setLoading(false);
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
            disabled={loading}
          >
            🔄 Перезагрузить бота
          </Button>
          <Button
            onClick={() => setAutoRefresh(!autoRefresh)}
            variant={autoRefresh ? "default" : "outline"}
          >
            {autoRefresh ? "🔄 Авто-обновление ON" : "⏸️ Авто-обновление OFF"}
          </Button>
          <Button onClick={loadData} variant="outline">
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
                  ${metrics.revenue.total.toFixed(2)}
                </div>
              </div>
              <div className="p-4 bg-blue-50 rounded-lg">
                <div className="text-sm text-gray-600">Средний заказ</div>
                <div className="text-3xl font-bold text-blue-600">
                  ${metrics.revenue.average_order.toFixed(2)}
                </div>
              </div>
              <div className="p-4 bg-purple-50 rounded-lg">
                <div className="text-sm text-gray-600">Активные пользователи</div>
                <div className="text-3xl font-bold text-purple-600">
                  {metrics.users.active_today}
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
