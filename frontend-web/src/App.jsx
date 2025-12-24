// src/App.jsx
import React from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import ReviewQueue from './pages/ReviewQueue'; // 确保这个路径正确
import TranscriptViewer from './pages/TranscriptViewer'; // ✨ 引入新组件
import Importer from './pages/Importer'; // ✨ 新引入
import Codebook from './pages/Codebook';
const { Header, Content, Sider } = Layout;


// ... (Menu items 配置保持不变，或者直接用下面的 Layout 代码) ...

const MainLayout = () => {
  const location = useLocation();
  // 定义菜单，key 对应路由路径
  const items = [
    { key: '/', label: <Link to="/">Importer</Link> },
    { key: '/viewer', label: <Link to="/viewer">Transcript Viewer</Link> }, // ✨
    { key: '/review', label: <Link to="/review">Review Queue</Link> },
    { key: '/codebook', label: <Link to="/codebook">Codebook</Link> },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible>
        <div style={{ height: 32, margin: 16, background: 'rgba(255, 255, 255, 0.2)', textAlign:'center', color:'white', lineHeight:'32px' }}>QualiAgent</div>
        <Menu theme="dark" mode="inline" selectedKeys={[location.pathname]} items={items} />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: 0, paddingLeft: 20, fontWeight:'bold' }}>AI Copilot Workbench</Header>
        <Content style={{ margin: '16px' }}>
          <div style={{ padding: 24, minHeight: 360, background: '#fff', borderRadius: 8 }}>
            <Routes> {/* ✨ 注意：这里把 Route 放到 Content 里面更合理 */}
              <Route path="/" element={<Importer />}/> {/* ✨ 这里不再是占位符了 */}
              <Route path="/viewer" element={<TranscriptViewer />} /> {/* ✨ 挂载这里 */}
              <Route path="/review" element={<ReviewQueue />} />
              <Route path="/codebook" element={<Codebook />} />
            </Routes>
          </div>
        </Content>
      </Layout>
    </Layout>
  );
};

function App() {
  return (
    <BrowserRouter>
      <MainLayout />
    </BrowserRouter>
  );
}

export default App;