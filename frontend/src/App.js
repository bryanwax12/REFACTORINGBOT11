import { useState, useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { toast, Toaster } from "sonner";
import { Package, DollarSign, Users, TrendingUp, Send, MapPin, Box, Search, Download, RefreshCw, FileText, Copy, ExternalLink } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [orders, setOrders] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [balanceModal, setBalanceModal] = useState({ open: false, telegram_id: null, action: null });
  const [balanceAmount, setBalanceAmount] = useState('');
  const [userDetailsModal, setUserDetailsModal] = useState({ open: false, details: null });
  const [leaderboard, setLeaderboard] = useState([]);
  const [showLeaderboard, setShowLeaderboard] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [refundModal, setRefundModal] = useState({ open: false, order: null });
  const [refundReason, setRefundReason] = useState('');
  const [trackingModal, setTrackingModal] = useState({ open: false, tracking: null, loading: false });
  const [discountModal, setDiscountModal] = useState({ open: false, user: null });
  const [discountValue, setDiscountValue] = useState('');
  const [expenseStats, setExpenseStats] = useState(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [statsRes, ordersRes, usersRes, leaderboardRes, expenseRes] = await Promise.all([
        axios.get(`${API}/stats`),
        axios.get(`${API}/orders`),
        axios.get(`${API}/users`),
        axios.get(`${API}/users/leaderboard`),
        axios.get(`${API}/stats/expenses`)
      ]);
      
      setStats(statsRes.data);
      setOrders(ordersRes.data);
      setUsers(usersRes.data);
      setLeaderboard(leaderboardRes.data);
      setExpenseStats(expenseRes.data);
    } catch (error) {
      toast.error("Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  const loadExpenseStats = async () => {
    try {
      const params = {};
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      
      const response = await axios.get(`${API}/stats/expenses`, { params });
      setExpenseStats(response.data);
    } catch (error) {
      toast.error("Failed to load expense stats");
    }
  };

  const searchOrders = async () => {
    if (!searchQuery.trim()) {
      loadData();
      return;
    }
    
    try {
      setLoading(true);
      const params = { query: searchQuery };
      if (statusFilter !== 'all') {
        params.payment_status = statusFilter;
      }
      
      const response = await axios.get(`${API}/orders/search`, { params });
      setOrders(response.data);
    } catch (error) {
      toast.error("Search failed");
    } finally {
      setLoading(false);
    }
  };

  const handleRefund = async () => {
    if (!refundModal.order) return;
    
    try {
      await axios.post(`${API}/orders/${refundModal.order.id}/refund`, null, {
        params: { refund_reason: refundReason || 'Admin refund' }
      });
      
      toast.success('Order refunded successfully');
      setRefundModal({ open: false, order: null });
      setRefundReason('');
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Refund failed');
    }
  };

  const exportToCSV = async () => {
    try {
      const params = {};
      if (statusFilter !== 'all') {
        params.payment_status = statusFilter;
      }
      
      const response = await axios.get(`${API}/orders/export/csv`, {
        params,
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `orders_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      
      toast.success('Orders exported successfully');
    } catch (error) {
      toast.error('Export failed');
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  const downloadLabel = async (order) => {
    if (!order.label_id) {
      toast.error('Label not available');
      return;
    }
    
    try {
      // Download via backend proxy
      const response = await axios.get(`${API}/labels/${order.label_id}/download`, {
        responseType: 'blob'
      });
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `label_${order.id.substring(0, 8)}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      
      toast.success('Label downloaded');
    } catch (error) {
      toast.error('Failed to download label');
    }
  };

  const fetchTrackingStatus = async (trackingNumber, carrier) => {
    if (!trackingNumber || !carrier) {
      toast.error('Tracking information not available');
      return;
    }
    
    setTrackingModal({ open: true, tracking: null, loading: true });
    
    try {
      const response = await axios.get(`${API}/shipping/track/${trackingNumber}`, {
        params: { carrier }
      });
      setTrackingModal({ open: true, tracking: response.data, loading: false });
    } catch (error) {
      toast.error('Failed to fetch tracking info');
      setTrackingModal({ open: false, tracking: null, loading: false });
    }
  };

  const handleSetDiscount = async () => {
    if (!discountModal.user) return;
    
    const discount = parseFloat(discountValue);
    if (isNaN(discount) || discount < 0 || discount > 100) {
      toast.error('Discount must be between 0 and 100');
      return;
    }
    
    try {
      await axios.post(`${API}/users/${discountModal.user.telegram_id}/discount`, null, {
        params: { discount }
      });
      
      toast.success(`Discount set to ${discount}%`);
      setDiscountModal({ open: false, user: null });
      setDiscountValue('');
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to set discount');
    }
  };

  const handleBalanceAction = (telegram_id, action) => {
    setBalanceModal({ open: true, telegram_id, action });
    setBalanceAmount('');
  };

  const viewUserDetails = async (telegram_id) => {
    try {
      const response = await axios.get(`${API}/users/${telegram_id}/details`);
      setUserDetailsModal({ open: true, details: response.data });
    } catch (error) {
      toast.error("Failed to load user details");
    }
  };

  const submitBalanceChange = async () => {
    const amount = parseFloat(balanceAmount);
    
    if (!amount || amount <= 0) {
      toast.error("Please enter a valid amount");
      return;
    }

    try {
      const endpoint = balanceModal.action === 'add' ? 'add' : 'deduct';
      const response = await axios.post(
        `${API}/users/${balanceModal.telegram_id}/balance/${endpoint}`,
        null,
        { params: { amount } }
      );
      
      toast.success(
        balanceModal.action === 'add' 
          ? `Added $${amount} to balance` 
          : `Deducted $${amount} from balance`
      );
      
      // Reload data
      loadData();
      setBalanceModal({ open: false, telegram_id: null, action: null });
      setBalanceAmount('');
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to update balance");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-emerald-500"></div>
      </div>
    );
  }

  return (
    <div className="space-y-8" data-testid="dashboard">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground mt-1">Shipping bot analytics and management</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        <Card data-testid="stat-users">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Users</CardTitle>
            <Users className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_users || 0}</div>
            <p className="text-xs text-muted-foreground mt-1">Registered via Telegram</p>
          </CardContent>
        </Card>

        <Card data-testid="stat-orders">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Orders</CardTitle>
            <Package className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_orders || 0}</div>
            <p className="text-xs text-muted-foreground mt-1">All time orders</p>
          </CardContent>
        </Card>

        <Card data-testid="stat-paid">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Paid Orders</CardTitle>
            <TrendingUp className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.paid_orders || 0}</div>
            <p className="text-xs text-muted-foreground mt-1">Successfully paid</p>
          </CardContent>
        </Card>

        <Card data-testid="stat-revenue">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Revenue</CardTitle>
            <DollarSign className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${stats?.total_revenue?.toFixed(2) || '0.00'}</div>
            <p className="text-xs text-muted-foreground mt-1">Total in USDT</p>
          </CardContent>
        </Card>

        <Card data-testid="stat-profit">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Profit</CardTitle>
            <TrendingUp className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">${stats?.total_profit?.toFixed(2) || '0.00'}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {stats?.total_labels || 0} labels × $10 each
            </p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview" data-testid="tab-overview">Overview</TabsTrigger>
          <TabsTrigger value="orders" data-testid="tab-orders">Orders</TabsTrigger>
          <TabsTrigger value="users" data-testid="tab-users">Users</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          {/* Expense Tracking Card */}
          <Card className="border-2 border-red-200 bg-red-50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-red-600" />
                💰 ShipStation Expenses (Real Costs)
              </CardTitle>
              <CardDescription>Money spent on labels (without $10 profit)</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div className="bg-white p-4 rounded-lg border border-red-200">
                  <p className="text-sm text-muted-foreground">Total Spent (All Time)</p>
                  <p className="text-3xl font-bold text-red-600">
                    ${expenseStats?.total_expense?.toFixed(2) || '0.00'}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {expenseStats?.labels_count || 0} labels created
                  </p>
                </div>
                
                <div className="bg-white p-4 rounded-lg border border-orange-200">
                  <p className="text-sm text-muted-foreground">Today's Expenses</p>
                  <p className="text-3xl font-bold text-orange-600">
                    ${expenseStats?.today_expense?.toFixed(2) || '0.00'}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {expenseStats?.today_labels || 0} labels today
                  </p>
                </div>
                
                <div className="bg-white p-4 rounded-lg border border-blue-200">
                  <p className="text-sm text-muted-foreground">Avg Cost per Label</p>
                  <p className="text-3xl font-bold text-blue-600">
                    ${expenseStats?.labels_count > 0 
                      ? (expenseStats.total_expense / expenseStats.labels_count).toFixed(2) 
                      : '0.00'}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Average shipping cost
                  </p>
                </div>
              </div>

              {/* Date Filter */}
              <div className="flex gap-4 items-end bg-white p-4 rounded-lg border">
                <div className="flex-1 space-y-2">
                  <Label htmlFor="date-from">From Date</Label>
                  <Input
                    id="date-from"
                    type="date"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                  />
                </div>
                <div className="flex-1 space-y-2">
                  <Label htmlFor="date-to">To Date</Label>
                  <Input
                    id="date-to"
                    type="date"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                  />
                </div>
                <Button onClick={loadExpenseStats}>
                  <Search className="h-4 w-4 mr-2" />
                  Filter
                </Button>
                <Button 
                  variant="outline" 
                  onClick={() => {
                    setDateFrom('');
                    setDateTo('');
                    loadData();
                  }}
                >
                  Reset
                </Button>
              </div>

              {(dateFrom || dateTo) && (
                <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                  <p className="text-sm font-medium text-blue-900">
                    📅 Filtered Period: 
                    {dateFrom && ` From ${new Date(dateFrom).toLocaleDateString()}`}
                    {dateTo && ` To ${new Date(dateTo).toLocaleDateString()}`}
                  </p>
                  <p className="text-xs text-blue-700 mt-1">
                    Total spent in this period: ${expenseStats?.total_expense?.toFixed(2) || '0.00'} 
                    ({expenseStats?.labels_count || 0} labels)
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Regular Stats Cards */}
        </TabsContent>

        <TabsContent value="orders" className="space-y-4">
          {/* Search and Filters */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex gap-4 items-end">
                <div className="flex-1 space-y-2">
                  <Label htmlFor="search">Search by Order ID or Tracking Number</Label>
                  <div className="flex gap-2">
                    <Input
                      id="search"
                      placeholder="Enter Order ID or Tracking #..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && searchOrders()}
                    />
                    <Button onClick={searchOrders} data-testid="search-btn">
                      <Search className="h-4 w-4 mr-2" />
                      Search
                    </Button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="status-filter">Payment Status</Label>
                  <select
                    id="status-filter"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  >
                    <option value="all">All</option>
                    <option value="paid">Paid</option>
                    <option value="pending">Pending</option>
                  </select>
                </div>
                <Button onClick={loadData} variant="outline" data-testid="refresh-btn">
                  <RefreshCw className="h-4 w-4" />
                </Button>
                <Button onClick={exportToCSV} variant="outline" data-testid="export-btn">
                  <Download className="h-4 w-4 mr-2" />
                  Export CSV
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Orders Table */}
          <Card>
            <CardHeader>
              <CardTitle>Orders ({orders.length})</CardTitle>
              <CardDescription>All shipping orders with tracking info</CardDescription>
            </CardHeader>
            <CardContent>
              {orders.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">No orders found</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="border-b">
                      <tr className="text-left">
                        <th className="pb-3 font-medium">User</th>
                        <th className="pb-3 font-medium">Order ID</th>
                        <th className="pb-3 font-medium">Tracking #</th>
                        <th className="pb-3 font-medium">Route</th>
                        <th className="pb-3 font-medium">Amount</th>
                        <th className="pb-3 font-medium">Status</th>
                        <th className="pb-3 font-medium">Delivery</th>
                        <th className="pb-3 font-medium">Date</th>
                        <th className="pb-3 font-medium text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orders.map((order, idx) => (
                        <tr key={`${order.id}-${order.label_id || idx}`} className="border-b last:border-0 hover:bg-muted/50" data-testid="order-row">
                          <td className="py-3">
                            <div className="text-xs">
                              <div className="font-medium">{order.user_name || 'Unknown'}</div>
                              <div className="text-muted-foreground">
                                @{order.user_username || 'no_username'}
                              </div>
                              <div className="text-muted-foreground">
                                ID: {order.telegram_id}
                              </div>
                            </div>
                          </td>
                          <td className="py-3">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs">{order.id.substring(0, 8)}</span>
                              <button
                                onClick={() => copyToClipboard(order.id)}
                                className="text-muted-foreground hover:text-foreground"
                                title="Copy Order ID"
                              >
                                <Copy className="h-3 w-3" />
                              </button>
                            </div>
                          </td>
                          <td className="py-3">
                            {order.tracking_number ? (
                              <div className="flex items-center gap-2">
                                <div>
                                  <div className="flex items-center gap-1">
                                    <span className="font-mono text-xs">{order.tracking_number}</span>
                                    <button
                                      onClick={() => copyToClipboard(order.tracking_number)}
                                      className="text-muted-foreground hover:text-foreground"
                                      title="Copy Tracking #"
                                    >
                                      <Copy className="h-3 w-3" />
                                    </button>
                                  </div>
                                  {order.label_created_at && (
                                    <div className="text-xs text-muted-foreground">
                                      Created: {new Date(order.label_created_at).toLocaleString()}
                                    </div>
                                  )}
                                </div>
                              </div>
                            ) : (
                              <span className="text-muted-foreground text-xs">-</span>
                            )}
                          </td>
                          <td className="py-3">
                            <div className="text-xs">
                              <div>{order.address_from.city}, {order.address_from.state}</div>
                              <div className="text-muted-foreground">→ {order.address_to.city}, {order.address_to.state}</div>
                            </div>
                          </td>
                          <td className="py-3 font-semibold">${order.amount}</td>
                          <td className="py-3">
                            <div className="flex flex-col gap-1">
                              <Badge variant={order.payment_status === 'paid' ? 'default' : 'secondary'} className="w-fit">
                                {order.payment_status}
                              </Badge>
                              <Badge variant="outline" className="w-fit text-xs">
                                {order.shipping_status}
                              </Badge>
                              {order.refund_status === 'refunded' && (
                                <Badge variant="destructive" className="w-fit text-xs">
                                  Refunded
                                </Badge>
                              )}
                            </div>
                          </td>
                          <td className="py-3">
                            {order.tracking_number && order.carrier ? (
                              <button
                                onClick={() => fetchTrackingStatus(order.tracking_number, order.carrier)}
                                className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                              >
                                <ExternalLink className="h-3 w-3" />
                                Track
                              </button>
                            ) : (
                              <span className="text-xs text-muted-foreground">-</span>
                            )}
                          </td>
                          <td className="py-3 text-xs text-muted-foreground">
                            {new Date(order.created_at).toLocaleDateString()}
                          </td>
                          <td className="py-3">
                            <div className="flex gap-1 justify-end">
                              {order.label_id && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => downloadLabel(order)}
                                  title="Download Label"
                                >
                                  <FileText className="h-4 w-4" />
                                </Button>
                              )}
                              {order.payment_status === 'paid' && order.refund_status !== 'refunded' && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => {
                                    setRefundModal({ open: true, order });
                                    setRefundReason('');
                                  }}
                                  title="Refund & Void Label"
                                  className="text-red-600 hover:text-red-700"
                                >
                                  <RefreshCw className="h-4 w-4" />
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="users" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Registered Users</CardTitle>
              <CardDescription>Users who started the Telegram bot</CardDescription>
            </CardHeader>
            <CardContent>
              {users.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">No users yet</p>
              ) : (
                <div className="space-y-4">
                  {users.map((user) => (
                    <div key={user.id} className="flex items-center justify-between border-b pb-4 last:border-0" data-testid="user-item">
                      <div className="flex-1">
                        <p className="font-medium">{user.first_name || 'Unknown'}</p>
                        <p className="text-sm text-muted-foreground">@{user.username || 'no_username'}</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          Telegram ID: {user.telegram_id}
                        </p>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <p className="text-sm font-semibold text-emerald-600">
                            Balance: ${(user.balance || 0).toFixed(2)}
                          </p>
                          {user.discount > 0 && (
                            <p className="text-xs font-medium text-purple-600">
                              🎉 Discount: {user.discount}%
                            </p>
                          )}
                          <p className="text-xs text-muted-foreground">
                            {new Date(user.created_at).toLocaleDateString()}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <Button 
                            size="sm" 
                            variant="ghost"
                            data-testid={`view-details-${user.telegram_id}`}
                            onClick={() => viewUserDetails(user.telegram_id)}
                          >
                            👁️ Details
                          </Button>
                          <Button 
                            size="sm" 
                            variant="outline"
                            data-testid={`add-balance-${user.telegram_id}`}
                            onClick={() => handleBalanceAction(user.telegram_id, 'add')}
                          >
                            💰 Add
                          </Button>
                          <Button 
                            size="sm" 
                            variant="outline"
                            data-testid={`deduct-balance-${user.telegram_id}`}
                            onClick={() => handleBalanceAction(user.telegram_id, 'deduct')}
                            disabled={(user.balance || 0) === 0}
                          >
                            ➖ Deduct
                          </Button>
                          <Button 
                            size="sm" 
                            variant="outline"
                            className="text-purple-600 border-purple-300 hover:bg-purple-50"
                            onClick={() => {
                              setDiscountModal({ open: true, user });
                              setDiscountValue(user.discount?.toString() || '0');
                            }}
                          >
                            🎁 Discount
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="leaderboard" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>User Leaderboard</CardTitle>
              <CardDescription>Top users ranked by activity and spending</CardDescription>
            </CardHeader>
            <CardContent>
              {leaderboard.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">No data yet</p>
              ) : (
                <div className="space-y-4">
                  {leaderboard.map((user, index) => (
                    <div key={user.telegram_id} className="flex items-center gap-4 border-b pb-4 last:border-0" data-testid="leaderboard-item">
                      <div className="text-2xl font-bold text-muted-foreground w-8">
                        {index + 1}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <p className="font-medium">{user.first_name}</p>
                          <Badge variant="outline">{user.rating_level}</Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">@{user.username || 'no_username'}</p>
                      </div>
                      <div className="text-right space-y-1">
                        <p className="text-sm font-semibold">{user.rating_score.toFixed(0)} points</p>
                        <p className="text-xs text-muted-foreground">{user.total_orders} orders • ${user.total_spent.toFixed(2)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* User Details Modal */}
      {userDetailsModal.open && userDetailsModal.details && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" data-testid="user-details-modal">
          <Card className="w-full max-w-4xl max-h-[90vh] overflow-y-auto">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    {userDetailsModal.details.user.first_name} 
                    <Badge variant="outline">{userDetailsModal.details.stats.rating_level}</Badge>
                  </CardTitle>
                  <CardDescription>
                    @{userDetailsModal.details.user.username || 'no_username'} • ID: {userDetailsModal.details.user.telegram_id}
                  </CardDescription>
                </div>
                <Button 
                  onClick={() => setUserDetailsModal({ open: false, details: null })}
                  variant="ghost"
                  size="sm"
                  data-testid="close-details-btn"
                >
                  ✕
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* User Stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-2xl font-bold">{userDetailsModal.details.stats.total_orders}</div>
                    <p className="text-xs text-muted-foreground">Total Orders</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-2xl font-bold">{userDetailsModal.details.stats.paid_orders}</div>
                    <p className="text-xs text-muted-foreground">Paid Orders</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-2xl font-bold">${userDetailsModal.details.stats.total_spent.toFixed(2)}</div>
                    <p className="text-xs text-muted-foreground">Total Spent</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-2xl font-bold">${userDetailsModal.details.stats.average_order_value.toFixed(2)}</div>
                    <p className="text-xs text-muted-foreground">Avg Order</p>
                  </CardContent>
                </Card>
              </div>

              {/* Orders History */}
              <div>
                <h3 className="font-semibold mb-4">Orders History</h3>
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {userDetailsModal.details.orders.length === 0 ? (
                    <p className="text-center text-muted-foreground py-4">No orders yet</p>
                  ) : (
                    userDetailsModal.details.orders.map((order) => (
                      <div key={order.id} className="border rounded-lg p-4 space-y-2">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium">Order #{order.id.substring(0, 8)}</p>
                            <p className="text-sm text-muted-foreground">
                              {new Date(order.created_at).toLocaleString()}
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="font-semibold">${order.amount}</p>
                            <div className="flex gap-2 mt-1">
                              <Badge variant={order.payment_status === 'paid' ? 'default' : 'secondary'}>
                                {order.payment_status}
                              </Badge>
                              <Badge variant="outline">{order.shipping_status}</Badge>
                            </div>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <p className="font-medium">From:</p>
                            <p className="text-muted-foreground">
                              {order.address_from.name}<br />
                              {order.address_from.street1}
                              {order.address_from.street2 && <>, {order.address_from.street2}</>}<br />
                              {order.address_from.city}, {order.address_from.state} {order.address_from.zip}
                            </p>
                          </div>
                          <div>
                            <p className="font-medium">To:</p>
                            <p className="text-muted-foreground">
                              {order.address_to.name}<br />
                              {order.address_to.street1}
                              {order.address_to.street2 && <>, {order.address_to.street2}</>}<br />
                              {order.address_to.city}, {order.address_to.state} {order.address_to.zip}
                            </p>
                          </div>
                        </div>
                        {order.selected_carrier && (
                          <p className="text-sm">
                            <span className="font-medium">Carrier:</span> {order.selected_carrier} - {order.selected_service}
                          </p>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Balance Management Modal */}
      {balanceModal.open && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="balance-modal">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>
                {balanceModal.action === 'add' ? '💰 Add Balance' : '➖ Deduct Balance'}
              </CardTitle>
              <CardDescription>
                Enter amount in USD for Telegram ID: {balanceModal.telegram_id}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="balance-amount">Amount (USD)</Label>
                <Input
                  id="balance-amount"
                  type="number"
                  step="0.01"
                  placeholder="10.00"
                  value={balanceAmount}
                  onChange={(e) => setBalanceAmount(e.target.value)}
                  data-testid="balance-amount-input"
                  autoFocus
                />
              </div>
              <div className="flex gap-2">
                <Button 
                  onClick={submitBalanceChange}
                  className="flex-1"
                  data-testid="confirm-balance-btn"
                >
                  {balanceModal.action === 'add' ? 'Add Balance' : 'Deduct Balance'}
                </Button>
                <Button 
                  onClick={() => setBalanceModal({ open: false, telegram_id: null, action: null })}
                  variant="outline"
                  data-testid="cancel-balance-btn"
                >
                  Cancel
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Refund Modal */}
      {refundModal.open && refundModal.order && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="refund-modal">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>🔄 Refund Order & Void Label</CardTitle>
              <CardDescription>
                Order #{refundModal.order.id.substring(0, 8)} - ${refundModal.order.amount}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm">
                <p className="font-medium text-yellow-900">This will:</p>
                <ul className="list-disc list-inside text-yellow-800 mt-1">
                  <li>Void label on ShipStation (cancel shipment)</li>
                  <li>Return ${refundModal.order.amount} to user balance</li>
                  <li>Cancel shipping status</li>
                  <li>Notify user via Telegram</li>
                </ul>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="refund-reason">Reason (optional)</Label>
                <Input
                  id="refund-reason"
                  placeholder="e.g., Customer request, Wrong address..."
                  value={refundReason}
                  onChange={(e) => setRefundReason(e.target.value)}
                  data-testid="refund-reason-input"
                />
              </div>
              
              <div className="flex gap-2">
                <Button 
                  onClick={handleRefund}
                  className="flex-1 bg-red-600 hover:bg-red-700"
                  data-testid="confirm-refund-btn"
                >
                  Confirm Refund
                </Button>
                <Button 
                  onClick={() => {
                    setRefundModal({ open: false, order: null });
                    setRefundReason('');
                  }}
                  variant="outline"
                  data-testid="cancel-refund-btn"
                >
                  Cancel
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tracking Status Modal */}
      {trackingModal.open && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="tracking-modal">
          <Card className="w-full max-w-2xl mx-4">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>📦 Tracking Information</CardTitle>
                <Button 
                  onClick={() => setTrackingModal({ open: false, tracking: null, loading: false })}
                  variant="ghost"
                  size="sm"
                >
                  ✕
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {trackingModal.loading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-emerald-500"></div>
                </div>
              ) : trackingModal.tracking ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-muted-foreground">Tracking Number</p>
                      <p className="font-mono text-sm font-medium">{trackingModal.tracking.tracking_number}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Carrier</p>
                      <p className="text-sm font-medium">{trackingModal.tracking.carrier}</p>
                    </div>
                  </div>
                  
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">Delivery Status</p>
                    <div className="flex items-center gap-3">
                      <div className="flex-1 bg-gray-200 rounded-full h-2">
                        <div 
                          className={`h-2 rounded-full transition-all`}
                          style={{
                            width: `${trackingModal.tracking.progress}%`,
                            backgroundColor: 
                              trackingModal.tracking.progress_color === 'green' ? '#10b981' :
                              trackingModal.tracking.progress_color === 'blue' ? '#3b82f6' :
                              trackingModal.tracking.progress_color === 'orange' ? '#f59e0b' :
                              trackingModal.tracking.progress_color === 'red' ? '#ef4444' : '#9ca3af'
                          }}
                        />
                      </div>
                      <span className="text-sm font-medium">{trackingModal.tracking.progress}%</span>
                    </div>
                    <p className="text-sm font-medium mt-2">{trackingModal.tracking.status_name}</p>
                    {trackingModal.tracking.carrier_status_description && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {trackingModal.tracking.carrier_status_description}
                      </p>
                    )}
                  </div>
                  
                  {trackingModal.tracking.estimated_delivery && (
                    <div>
                      <p className="text-sm text-muted-foreground">Estimated Delivery</p>
                      <p className="text-sm font-medium">
                        {new Date(trackingModal.tracking.estimated_delivery).toLocaleDateString()}
                      </p>
                    </div>
                  )}
                  
                  {trackingModal.tracking.tracking_events && trackingModal.tracking.tracking_events.length > 0 && (
                    <div>
                      <p className="text-sm text-muted-foreground mb-2">Recent Events</p>
                      <div className="space-y-2 max-h-48 overflow-y-auto">
                        {trackingModal.tracking.tracking_events.map((event, idx) => (
                          <div key={idx} className="border-l-2 border-gray-300 pl-3 pb-2">
                            <p className="text-xs font-medium">{event.description || event.status}</p>
                            <p className="text-xs text-muted-foreground">
                              {event.city && `${event.city}, `}{event.state}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {new Date(event.occurred_at || event.datetime).toLocaleString()}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-8">No tracking data available</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Discount Modal */}
      {discountModal.open && discountModal.user && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="discount-modal">
          <Card className="w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>🎁 Set User Discount</CardTitle>
              <CardDescription>
                User: {discountModal.user.first_name} (@{discountModal.user.username || 'no_username'})
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 text-sm">
                <p className="font-medium text-purple-900">Discount will apply to:</p>
                <ul className="list-disc list-inside text-purple-800 mt-1">
                  <li>All future orders</li>
                  <li>Final price after markup</li>
                  <li>User will be notified in Telegram</li>
                </ul>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="discount-value">Discount Percentage</Label>
                <Input
                  id="discount-value"
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  placeholder="10"
                  value={discountValue}
                  onChange={(e) => setDiscountValue(e.target.value)}
                  data-testid="discount-value-input"
                />
                <p className="text-xs text-muted-foreground">
                  Enter 0 to remove discount. Maximum 100%.
                </p>
              </div>
              
              <div className="flex gap-2">
                <Button 
                  onClick={handleSetDiscount}
                  className="flex-1 bg-purple-600 hover:bg-purple-700"
                  data-testid="confirm-discount-btn"
                >
                  Set Discount
                </Button>
                <Button 
                  onClick={() => {
                    setDiscountModal({ open: false, user: null });
                    setDiscountValue('');
                  }}
                  variant="outline"
                  data-testid="cancel-discount-btn"
                >
                  Cancel
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

const CreateOrder = () => {
  const [formData, setFormData] = useState({
    telegram_id: '',
    amount: '',
    address_from: {
      name: '',
      street1: '',
      city: '',
      state: '',
      zip: '',
      country: 'US',
      phone: '',
      email: ''
    },
    address_to: {
      name: '',
      street1: '',
      city: '',
      state: '',
      zip: '',
      country: 'US',
      phone: '',
      email: ''
    },
    parcel: {
      length: '5',
      width: '5',
      height: '5',
      weight: '2',
      distance_unit: 'in',
      mass_unit: 'lb'
    }
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const payload = {
        telegram_id: parseInt(formData.telegram_id),
        amount: parseFloat(formData.amount),
        address_from: formData.address_from,
        address_to: formData.address_to,
        parcel: {
          ...formData.parcel,
          length: parseFloat(formData.parcel.length),
          width: parseFloat(formData.parcel.width),
          height: parseFloat(formData.parcel.height),
          weight: parseFloat(formData.parcel.weight)
        }
      };
      
      const response = await axios.post(`${API}/orders`, payload);
      setResult(response.data);
      toast.success("Order created! Payment link sent to user.");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to create order");
    } finally {
      setLoading(false);
    }
  };

  const updateAddressField = (type, field, value) => {
    setFormData(prev => ({
      ...prev,
      [type]: {
        ...prev[type],
        [field]: value
      }
    }));
  };

  const updateParcelField = (field, value) => {
    setFormData(prev => ({
      ...prev,
      parcel: {
        ...prev.parcel,
        [field]: value
      }
    }));
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8" data-testid="create-order-form">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Create New Order</h1>
        <p className="text-muted-foreground mt-1">Create shipping order with crypto payment</p>
      </div>

      {result && (
        <Card className="bg-emerald-50 border-emerald-200">
          <CardHeader>
            <CardTitle className="text-emerald-900">Order Created!</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-sm"><strong>Order ID:</strong> {result.order_id}</p>
            <p className="text-sm"><strong>Amount:</strong> {result.amount} {result.currency}</p>
            {result.payment_url && (
              <div>
                <p className="text-sm font-medium mb-2">Payment URL:</p>
                <a href={result.payment_url} target="_blank" rel="noopener noreferrer" 
                   className="text-sm text-emerald-600 hover:underline break-all">
                  {result.payment_url}
                </a>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <form onSubmit={handleSubmit} className="space-y-8">
        <Card>
          <CardHeader>
            <CardTitle>Order Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="telegram_id">Telegram ID *</Label>
                <Input
                  id="telegram_id"
                  data-testid="input-telegram-id"
                  value={formData.telegram_id}
                  onChange={(e) => setFormData({...formData, telegram_id: e.target.value})}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="amount">Amount (USDT) *</Label>
                <Input
                  id="amount"
                  type="number"
                  step="0.01"
                  data-testid="input-amount"
                  value={formData.amount}
                  onChange={(e) => setFormData({...formData, amount: e.target.value})}
                  required
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>From Address</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Name *</Label>
                <Input
                  data-testid="from-name"
                  value={formData.address_from.name}
                  onChange={(e) => updateAddressField('address_from', 'name', e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>Phone</Label>
                <Input
                  data-testid="from-phone"
                  value={formData.address_from.phone}
                  onChange={(e) => updateAddressField('address_from', 'phone', e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Street Address *</Label>
              <Input
                data-testid="from-street"
                value={formData.address_from.street1}
                onChange={(e) => updateAddressField('address_from', 'street1', e.target.value)}
                required
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>City *</Label>
                <Input
                  data-testid="from-city"
                  value={formData.address_from.city}
                  onChange={(e) => updateAddressField('address_from', 'city', e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>State *</Label>
                <Input
                  data-testid="from-state"
                  value={formData.address_from.state}
                  onChange={(e) => updateAddressField('address_from', 'state', e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>ZIP *</Label>
                <Input
                  data-testid="from-zip"
                  value={formData.address_from.zip}
                  onChange={(e) => updateAddressField('address_from', 'zip', e.target.value)}
                  required
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>To Address</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Name *</Label>
                <Input
                  data-testid="to-name"
                  value={formData.address_to.name}
                  onChange={(e) => updateAddressField('address_to', 'name', e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>Phone</Label>
                <Input
                  data-testid="to-phone"
                  value={formData.address_to.phone}
                  onChange={(e) => updateAddressField('address_to', 'phone', e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Street Address *</Label>
              <Input
                data-testid="to-street"
                value={formData.address_to.street1}
                onChange={(e) => updateAddressField('address_to', 'street1', e.target.value)}
                required
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>City *</Label>
                <Input
                  data-testid="to-city"
                  value={formData.address_to.city}
                  onChange={(e) => updateAddressField('address_to', 'city', e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>State *</Label>
                <Input
                  data-testid="to-state"
                  value={formData.address_to.state}
                  onChange={(e) => updateAddressField('address_to', 'state', e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>ZIP *</Label>
                <Input
                  data-testid="to-zip"
                  value={formData.address_to.zip}
                  onChange={(e) => updateAddressField('address_to', 'zip', e.target.value)}
                  required
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Parcel Details</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label>Length (in)</Label>
                <Input
                  type="number"
                  step="0.1"
                  data-testid="parcel-length"
                  value={formData.parcel.length}
                  onChange={(e) => updateParcelField('length', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Width (in)</Label>
                <Input
                  type="number"
                  step="0.1"
                  data-testid="parcel-width"
                  value={formData.parcel.width}
                  onChange={(e) => updateParcelField('width', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Height (in)</Label>
                <Input
                  type="number"
                  step="0.1"
                  data-testid="parcel-height"
                  value={formData.parcel.height}
                  onChange={(e) => updateParcelField('height', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Weight (lb)</Label>
                <Input
                  type="number"
                  step="0.1"
                  data-testid="parcel-weight"
                  value={formData.parcel.weight}
                  onChange={(e) => updateParcelField('weight', e.target.value)}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Button type="submit" className="w-full" disabled={loading} data-testid="submit-order-btn">
          {loading ? (
            <span className="flex items-center gap-2">
              <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white"></div>
              Creating Order...
            </span>
          ) : (
            <span className="flex items-center gap-2">
              <Send className="h-4 w-4" />
              Create Order
            </span>
          )}
        </Button>
      </form>
    </div>
  );
};

const Home = () => {
  return (
    <div className="min-h-screen">
      <nav className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Box className="h-6 w-6 text-emerald-500" />
              <span className="font-bold text-xl">ShippoBot</span>
            </div>
            <div className="flex gap-4">
              <Link to="/">
                <Button variant="ghost" data-testid="nav-dashboard">Dashboard</Button>
              </Link>
              <Link to="/create">
                <Button variant="ghost" data-testid="nav-create">Create Order</Button>
              </Link>
            </div>
          </div>
        </div>
      </nav>

      <main className="container mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/create" element={<CreateOrder />} />
        </Routes>
      </main>
    </div>
  );
};

function App() {
  return (
    <div className="App">
      <Toaster position="top-right" richColors />
      <BrowserRouter>
        <Home />
      </BrowserRouter>
    </div>
  );
}

export default App;