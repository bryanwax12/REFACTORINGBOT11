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
import { Package, DollarSign, Users, TrendingUp, Send, MapPin, Box } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [orders, setOrders] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [balanceModal, setBalanceModal] = useState({ open: false, telegram_id: null, action: null });
  const [balanceAmount, setBalanceAmount] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [statsRes, ordersRes, usersRes] = await Promise.all([
        axios.get(`${API}/stats`),
        axios.get(`${API}/orders`),
        axios.get(`${API}/users`)
      ]);
      
      setStats(statsRes.data);
      setOrders(ordersRes.data);
      setUsers(usersRes.data);
    } catch (error) {
      toast.error("Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  const handleBalanceAction = (telegram_id, action) => {
    setBalanceModal({ open: true, telegram_id, action });
    setBalanceAmount('');
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
      </div>

      <Tabs defaultValue="orders" className="space-y-6">
        <TabsList>
          <TabsTrigger value="orders" data-testid="tab-orders">Orders</TabsTrigger>
          <TabsTrigger value="users" data-testid="tab-users">Users</TabsTrigger>
        </TabsList>

        <TabsContent value="orders" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Recent Orders</CardTitle>
              <CardDescription>All shipping orders from Telegram bot</CardDescription>
            </CardHeader>
            <CardContent>
              {orders.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">No orders yet</p>
              ) : (
                <div className="space-y-4">
                  {orders.map((order) => (
                    <div key={order.id} className="flex items-center justify-between border-b pb-4 last:border-0" data-testid="order-item">
                      <div className="space-y-1">
                        <p className="font-medium">Order #{order.id.substring(0, 8)}</p>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <MapPin className="h-3 w-3" />
                          <span>{order.address_from.city} → {order.address_to.city}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant={order.payment_status === 'paid' ? 'default' : 'secondary'}>
                            {order.payment_status}
                          </Badge>
                          <Badge variant="outline">{order.shipping_status}</Badge>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold">${order.amount}</p>
                        <p className="text-xs text-muted-foreground">{new Date(order.created_at).toLocaleDateString()}</p>
                      </div>
                    </div>
                  ))}
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
                          <p className="text-xs text-muted-foreground">
                            {new Date(user.created_at).toLocaleDateString()}
                          </p>
                        </div>
                        <div className="flex gap-2">
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
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

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