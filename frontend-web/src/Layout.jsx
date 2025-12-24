// src/Layout.jsx
import React from 'react';
import { Layout, Menu } from 'antd';
import { UploadOutlined, ProfileOutlined, ReadOutlined, BookOutlined } from '@ant-design/icons';
import { Link, Outlet, useLocation } from 'react-router-dom';

const { Header, Content, Sider } = Layout;

const items = [
  { key: '/', icon: <UploadOutlined />, label: <Link to="/">Importer</Link> },
  { key: '/viewer', icon: <ReadOutlined />, label: <Link to="/viewer">Transcript Viewer</Link> },
  { key: '/review', icon: <ProfileOutlined />, label: <Link to="/review">Review Queue</Link> },
  { key: '/codebook', icon: <BookOutlined />, label: <Link to="/codebook">Codebook</Link> },
];

const MainLayout = () => {
  const location = useLocation();

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible breakpoint="lg">
        <div style={{ height: 32, margin: 16, background: 'rgba(255, 255, 255, 0.2)', textAlign:'center', color:'white', lineHeight:'32px', fontWeight:'bold' }}>
          QualiAgent
        </div>
        <Menu theme="dark" mode="inline" selectedKeys={[location.pathname]} items={items} />
      </Sider>
      <Layout>
        <Header style={{ padding: 0, background: '#fff', paddingLeft: 20, fontWeight: 'bold', fontSize: 16 }}>
          AI Copilot Workbench
        </Header>
        <Content style={{ margin: '16px' }}>
          <div style={{ padding: 24, minHeight: 360, background: '#fff', borderRadius: 8 }}>
            <Outlet /> {/* 路由内容渲染在这里 */}
          </div>
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;