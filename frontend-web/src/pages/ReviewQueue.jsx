// src/pages/ReviewQueue.jsx
import React, { useState, useEffect } from 'react';
import {
  Layout, Typography, Button, Card, Tag,
  Space, Empty, message, Spin, Modal
} from 'antd';
import {
  CheckOutlined, CloseOutlined, ReloadOutlined,
  CheckCircleOutlined, DeleteOutlined
} from '@ant-design/icons';
import axios from 'axios';

const { Content } = Layout;
const { Title, Text, Paragraph } = Typography;
const { confirm } = Modal;

const ReviewQueue = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // 1. 获取列表
  const fetchQueue = async () => {
    setLoading(true);
    try {
      const res = await axios.get('http://localhost:8000/review/queue');
      setItems(res.data);
    } catch (err) {
      console.error(err);
      message.error("Failed to load review queue");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
  }, []);

  // 2. 单个处理
  const handleReview = async (eventId, action) => {
    try {
      // 乐观更新：先从界面移除
      setItems(prev => prev.filter(item => item.event_id !== eventId));

      await axios.post(`http://localhost:8000/review/${eventId}`, { action });
      message.success(action === 'accept' ? "Accepted" : "Rejected");
    } catch (err) {
      message.error("Operation failed");
      fetchQueue(); // 失败回滚
    }
  };

  // 3. ✨✨✨ 批量处理 ✨✨✨
  const handleBatch = (action) => {
    const actionName = action === 'accept_all' ? 'Accept All' : 'Reject All';
    const isReject = action === 'reject_all';

    confirm({
      title: `Confirm ${actionName}?`,
      icon: isReject ? <DeleteOutlined style={{ color: 'red' }} /> : <CheckCircleOutlined style={{ color: 'green' }} />,
      content: `Are you sure you want to ${isReject ? 'REJECT' : 'ACCEPT'} all ${items.length} items in the queue?`,
      okText: 'Yes, Do it',
      okType: isReject ? 'danger' : 'primary',
      cancelText: 'Cancel',
      onOk: async () => {
        setActionLoading(true);
        try {
          const res = await axios.post('http://localhost:8000/review/queue/batch', { action });
          message.success(`Successfully processed ${res.data.count} items.`);
          fetchQueue(); // 刷新列表
        } catch (err) {
          message.error("Batch operation failed");
        } finally {
          setActionLoading(false);
        }
      },
    });
  };

  return (
    <Layout style={{ padding: '24px', background: '#f0f2f5', minHeight: '100vh' }}>
      <div style={{ maxWidth: 800, margin: '0 auto', width: '100%' }}>

        {/* Header Area */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <div style={{display: 'flex', alignItems: 'center', gap: 10}}>
             <span style={{fontSize: 24}}>🧐</span>
             <Title level={3} style={{ margin: 0 }}>Review Queue</Title>
             <Tag color="blue" style={{borderRadius: 10, padding: '0 8px'}}>{items.length}</Tag>
          </div>

          <Space>
            {/* ✨ 批量按钮组 */}
            {items.length > 0 && (
              <>
                <Button
                  danger
                  icon={<DeleteOutlined />}
                  loading={actionLoading}
                  onClick={() => handleBatch('reject_all')}
                >
                  Reject All
                </Button>
                <Button
                  type="primary"
                  icon={<CheckCircleOutlined />}
                  loading={actionLoading}
                  onClick={() => handleBatch('accept_all')}
                  style={{ backgroundColor: '#52c41a', borderColor: '#52c41a' }}
                >
                  Accept All
                </Button>
              </>
            )}
            <Button icon={<ReloadOutlined />} onClick={fetchQueue}>Refresh</Button>
          </Space>
        </div>

        {/* Content Area */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: 50 }}>
            <Spin size="large" />
          </div>
        ) : items.length === 0 ? (
          <Empty description="No pending items. Good job!" />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {items.map(item => (
              <Card
                key={item.event_id}
                bordered={false}
                style={{ borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.05)' }}
                bodyStyle={{ padding: 24 }}
              >
                <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>
                  Transcript Excerpt:
                </Text>
                <div style={{
                  background: '#fafafa', padding: '12px 16px', borderRadius: 6,
                  marginTop: 8, marginBottom: 16, fontStyle: 'italic', color: '#666'
                }}>
                  "{item.segment_text}"
                </div>

                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                  <div style={{ fontSize: 24, color: '#faad14' }}>💡</div>
                  <div style={{ flex: 1 }}>
                    <Text strong style={{ fontSize: 16, display: 'block', marginBottom: 4 }}>
                      {item.summary}
                    </Text>
                    <Tag color="blue" style={{ fontSize: 14, padding: '4px 10px' }}>
                      #{item.code_name}
                    </Tag>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 24, borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
                  <Button
                    danger
                    type="text"
                    icon={<CloseOutlined />}
                    onClick={() => handleReview(item.event_id, 'reject')}
                  >
                    Reject
                  </Button>
                  <Button
                    type="primary"
                    icon={<CheckOutlined />}
                    onClick={() => handleReview(item.event_id, 'accept')}
                  >
                    Accept
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
};

export default ReviewQueue;