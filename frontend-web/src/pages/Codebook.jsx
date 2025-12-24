// src/pages/Codebook.jsx
import React, { useState, useEffect } from 'react';
import {
  Layout, Typography, Button, Table, Tag,
  Space, Modal, Form, Input, message, Empty, Menu
} from 'antd';
import {
  PlusOutlined, ReloadOutlined, RobotOutlined,
  DeleteOutlined, BookOutlined, FolderAddOutlined
} from '@ant-design/icons';
import axios from 'axios';

const { Sider, Content } = Layout;
const { Title, Text } = Typography;
const { TextArea } = Input;

const CodebookPage = () => {
  // --- States ---
  // 1. 库列表状态
  const [libraries, setLibraries] = useState([]);
  const [selectedLibId, setSelectedLibId] = useState(null);
  const [isLibModalOpen, setIsLibModalOpen] = useState(false);

  // 2. 编码列表状态
  const [codes, setCodes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isCodeModalOpen, setIsCodeModalOpen] = useState(false);

  const [form] = Form.useForm();
  const [libForm] = Form.useForm();

  // --- Initialization ---
  useEffect(() => {
    fetchLibraries();
  }, []);

  useEffect(() => {
    if (selectedLibId) {
      fetchCodes(selectedLibId);
    } else {
      setCodes([]);
    }
  }, [selectedLibId]);

  // --- API Actions: Libraries ---
  const fetchLibraries = async () => {
    try {
      // 1. 初始化默认库 (防止空)
      await axios.post('http://localhost:8000/codebook/libraries/init_default');
      // 2. 获取列表
      const res = await axios.get('http://localhost:8000/codebook/libraries');
      setLibraries(res.data);

      // 如果当前没选中，或者选中的不在列表里了，默认选第一个
      if (res.data.length > 0 && (!selectedLibId || !res.data.find(l => l.id === selectedLibId))) {
        setSelectedLibId(res.data[0].id);
      }
    } catch (err) {
      message.error("Failed to load libraries");
    }
  };

  const handleCreateLibrary = async (values) => {
    try {
      await axios.post('http://localhost:8000/codebook/libraries', values);
      message.success("New Codebook Project Created");
      setIsLibModalOpen(false);
      libForm.resetFields();
      fetchLibraries(); // 刷新列表
    } catch (err) {
      message.error("Failed to create library");
    }
  };

  // --- API Actions: Codes ---
  const fetchCodes = async (libId) => {
    if (!libId) return;
    setLoading(true);
    try {
      // ✨ 关键：带上 library_id 参数
      const res = await axios.get(`http://localhost:8000/codebook/?library_id=${libId}`);
      setCodes(res.data);
    } catch (err) {
      message.error("Failed to load codes");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCode = async (values) => {
    if (!selectedLibId) return message.error("Please select a library first");
    try {
      await axios.post('http://localhost:8000/codebook/', {
        ...values,
        library_id: selectedLibId // ✨ 关键：把新 Code 存入当前库
      });
      message.success("Code added");
      setIsCodeModalOpen(false);
      form.resetFields();
      fetchCodes(selectedLibId);
    } catch (err) {
      message.error("Failed to add code");
    }
  };

  const handleDeleteCode = async (id) => {
    try {
      await axios.delete(`http://localhost:8000/codebook/${id}`);
      message.success("Code deleted");
      fetchCodes(selectedLibId);
    } catch (err) {
      message.error("Failed to delete");
    }
  };

  // --- Table Columns ---
  const columns = [
    {
      title: 'Code Name',
      dataIndex: 'code',
      key: 'code',
      render: (text) => <Tag color="blue" style={{fontSize: 14, padding: '4px 8px'}}>{text}</Tag>
    },
    {
      title: 'Definition',
      dataIndex: 'definition',
      key: 'definition',
      render: (text) => <Text style={{color: '#666'}}>{text || '-'}</Text>
    },
    {
      title: 'Usage',
      dataIndex: 'usage_count',
      key: 'usage_count',
      sorter: (a, b) => a.usage_count - b.usage_count,
      render: (count) => <Tag>{count}</Tag>
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Button
          type="text"
          danger
          icon={<DeleteOutlined />}
          onClick={() => handleDeleteCode(record.id)}
        />
      )
    }
  ];

  return (
    <Layout style={{ height: 'calc(100vh - 64px)', background: '#fff' }}>

      {/* --- 左侧边栏：库列表 --- */}
      <Sider width={250} theme="light" style={{borderRight: '1px solid #f0f0f0'}}>
        <div style={{padding: '16px', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
          <Text strong><BookOutlined /> Codebooks</Text>
          <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => setIsLibModalOpen(true)} />
        </div>

        <Menu
          mode="inline"
          selectedKeys={[selectedLibId]}
          onClick={(e) => setSelectedLibId(e.key)}
          style={{border: 'none'}}
          items={libraries.map(lib => ({
            key: lib.id,
            label: (
              <div style={{display:'flex', justifyContent:'space-between'}}>
                <span>{lib.name}</span>
                <Tag style={{marginRight:0}}>{lib.code_count}</Tag>
              </div>
            )
          }))}
        />
      </Sider>

      {/* --- 右侧内容：编码表格 --- */}
      <Content style={{ padding: '24px', overflowY: 'auto' }}>
        <div style={{ maxWidth: 1000, margin: '0 auto' }}>

          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
            <div>
              <Title level={3} style={{ margin: 0 }}>
                {libraries.find(l => l.id === selectedLibId)?.name || "Codebook Manager"}
              </Title>
              <Text type="secondary">Manage your qualitative codes and definitions.</Text>
            </div>
            <Space>
              <Button icon={<ReloadOutlined />} onClick={() => fetchCodes(selectedLibId)}>Refresh</Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setIsCodeModalOpen(true)}>New Code</Button>
            </Space>
          </div>

          {/* Table */}
          <Table
            columns={columns}
            dataSource={codes}
            rowKey="id"
            loading={loading}
            locale={{ emptyText: <Empty description="No codes in this library yet" /> }}
            pagination={{ pageSize: 8 }}
          />
        </div>
      </Content>

      {/* --- Modal: New Code --- */}
      <Modal
        title="Add New Code"
        open={isCodeModalOpen}
        onCancel={() => setIsCodeModalOpen(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleCreateCode}>
          <Form.Item name="code" label="Code Name" rules={[{ required: true }]}>
            <Input placeholder="e.g. Financial Anxiety" />
          </Form.Item>
          <Form.Item name="definition" label="Definition">
            <TextArea rows={3} placeholder="Describe what this code means..." />
          </Form.Item>
        </Form>
      </Modal>

      {/* --- Modal: New Library --- */}
      <Modal
        title="Create New Project Codebook"
        open={isLibModalOpen}
        onCancel={() => setIsLibModalOpen(false)}
        onOk={() => libForm.submit()}
      >
        <Form form={libForm} layout="vertical" onFinish={handleCreateLibrary}>
          <Form.Item name="name" label="Project Name" rules={[{ required: true }]}>
            <Input placeholder="e.g. Interview Phase 2" />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

    </Layout>
  );
};

export default CodebookPage;