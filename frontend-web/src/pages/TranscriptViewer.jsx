// src/pages/TranscriptViewer.jsx
import React, { useState, useEffect } from 'react';
import {
  Layout, Typography, Button, Spin, Empty,
  message, Tag, Popover, Radio, Divider, Select
} from 'antd';
import {
  RobotOutlined, FileTextOutlined,
  ThunderboltOutlined, LoadingOutlined, BookOutlined
} from '@ant-design/icons';
import axios from 'axios';

const { Sider, Content } = Layout;
const { Text, Title } = Typography;
const { Option } = Select;

const TranscriptViewer = () => {
  const [transcripts, setTranscripts] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [segments, setSegments] = useState([]);
  const [loading, setLoading] = useState(false);

  // AI Settings
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [targetSpeaker, setTargetSpeaker] = useState("受访者");
  const [density, setDensity] = useState("balanced");

  // ✨✨✨ 新增：Codebook Library 状态 ✨✨✨
  const [libraries, setLibraries] = useState([]);
  const [selectedLibId, setSelectedLibId] = useState(null);

  // 1. 初始化：获取文件列表 + 编码库列表
  useEffect(() => {
    fetchTranscripts();
    fetchLibraries(); // 获取库
    const intervalId = setInterval(fetchTranscripts, 2000);
    return () => clearInterval(intervalId);
  }, []);

  const fetchTranscripts = () => {
    axios.get('http://localhost:8000/transcripts/')
      .then(res => setTranscripts(res.data))
      .catch(err => console.error(err));
  };

  const fetchLibraries = async () => {
    try {
      // 1. 尝试初始化默认库 (防止第一次用报错)
      await axios.post('http://localhost:8000/codebook/libraries/init_default');
      // 2. 获取列表
      const res = await axios.get('http://localhost:8000/codebook/libraries');
      setLibraries(res.data);
      if (res.data.length > 0) {
        setSelectedLibId(res.data[0].id); // 默认选中第一个
      }
    } catch (err) {
      console.error("Failed to load libraries", err);
    }
  };

  // 2. 获取内容
  useEffect(() => {
    if (!activeId) return;
    setLoading(true);
    axios.get(`http://localhost:8000/segments/${activeId}`)
      .then(res => setSegments(Array.isArray(res.data) ? res.data : []))
      .catch(() => setSegments([]))
      .finally(() => setLoading(false));
  }, [activeId]);

  // 3. AI 分析
  const handleRunAI = async () => {
    if (!activeId || !selectedLibId) {
      message.error("请选择一个 Codebook");
      return;
    }
    setPopoverOpen(false);
    message.loading({ content: 'AI 任务已提交...', key: 'ai_run' });

    setTranscripts(prev => prev.map(t => t.id === activeId ? { ...t, status: 'processing' } : t));

    try {
      // ✨✨✨ 传参增加 library_id ✨✨✨
      await axios.post(
        `http://localhost:8000/events_v2/batch_ai/${activeId}?library_id=${selectedLibId}&target_speaker=${targetSpeaker}&density=${density}`
      );
      message.success({ content: "任务已开始", key: 'ai_run' });
    } catch (err) {
      message.error({ content: "AI 请求失败", key: 'ai_run' });
      fetchTranscripts();
    }
  };

  // AI 设置面板
  const aiSettingsContent = (
    <div style={{ width: 320 }}>
      {/* ✨✨✨ 新增：选择 Codebook ✨✨✨ */}
      <div style={{marginBottom:15}}>
        <Text strong><BookOutlined /> 选择编码库 (Codebook):</Text>
        <Select
          style={{width: '100%', marginTop: 5}}
          value={selectedLibId}
          onChange={setSelectedLibId}
          placeholder="Select a Codebook"
        >
          {libraries.map(lib => (
            <Option key={lib.id} value={lib.id}>{lib.name} ({lib.code_count})</Option>
          ))}
        </Select>
      </div>

      <div style={{marginBottom:15}}>
        <Text strong>分析对象:</Text>
        <Radio.Group value={targetSpeaker} onChange={e => setTargetSpeaker(e.target.value)} size="small" style={{marginTop:5, display: 'flex'}}>
          <Radio.Button value="受访者">受访者</Radio.Button>
          <Radio.Button value="访谈者">访谈者</Radio.Button>
        </Radio.Group>
      </div>

      <div style={{marginBottom:15}}>
        <Text strong>编码密度:</Text>
        <Radio.Group value={density} onChange={e => setDensity(e.target.value)} style={{display:'flex', flexDirection:'column', gap:5, marginTop:5}}>
          <Radio value="broad">Broad (概括)</Radio>
          <Radio value="balanced">Balanced (标准)</Radio>
          <Radio value="dense">Dense (详细)</Radio>
        </Radio.Group>
      </div>

      <Button type="primary" block onClick={handleRunAI} icon={<ThunderboltOutlined />}>开始分析</Button>
    </div>
  );

  const renderMainContent = () => {
    if (loading) return <div style={{textAlign:'center', marginTop:50}}><Spin size="large" /></div>;
    if (!segments || segments.length === 0) return <Empty description="暂无数据" />;

    return (
      <div style={{background: '#fff', padding: 30, borderRadius: 8}}>
        {segments.map((seg, idx) => (
            <div key={seg.id || idx} style={{marginBottom: 32}}>
                <div style={{marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8}}>
                    <Tag color={seg.speaker?.includes('访谈') ? 'blue' : seg.speaker?.includes('受访') ? 'green' : 'default'}>
                        {seg.speaker || 'Unknown'}
                    </Tag>
                    <Text type="secondary" style={{fontSize: 12}}>#{seg.index}</Text>
                </div>
                <div style={{fontSize: 16, lineHeight: 1.8, color: '#333', paddingLeft: 4}}>
                    {seg.text}
                </div>
                {seg.events && seg.events.length > 0 && (
                    <div style={{marginTop: 12, padding: '8px 12px', background: '#f9f9f9', borderLeft: '3px solid #faad14'}}>
                        <div style={{display: 'flex', flexWrap: 'wrap', gap: 6}}>
                            {seg.events.map((evt, eIdx) => (
                                <Tag key={eIdx} color="orange">{evt.code_name || evt.summary}</Tag>
                            ))}
                        </div>
                    </div>
                )}
                <Divider style={{margin: '24px 0 0 0'}} dashed />
            </div>
        ))}
      </div>
    );
  };

  return (
    <Layout style={{ height: 'calc(100vh - 64px)', background: '#fff' }}>
      <Sider width={260} theme="light" style={{borderRight:'1px solid #f0f0f0', display: 'flex', flexDirection: 'column'}}>
        <div style={{padding:'16px 20px', borderBottom:'1px solid #f0f0f0', display: 'flex', alignItems: 'center', gap: 8}}>
          <FileTextOutlined style={{fontSize: 18, color: '#1890ff'}} />
          <Text strong style={{fontSize: 16}}>文件列表</Text>
        </div>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {transcripts.map((item) => (
            <div
              key={item.id}
              onClick={() => setActiveId(item.id)}
              style={{
                padding: '12px 20px', cursor: 'pointer', borderBottom: '1px solid #f9f9f9',
                backgroundColor: activeId === item.id ? '#e6f7ff' : 'transparent',
                borderRight: activeId === item.id ? '3px solid #1890ff' : '3px solid transparent',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center'
              }}
            >
              <Text ellipsis style={{maxWidth: 140, color: activeId === item.id ? '#1890ff' : 'inherit'}}>
                {item.id}
              </Text>
              {item.status === 'processing' && <Tag icon={<LoadingOutlined />} color="blue" style={{fontSize:10}}>AI</Tag>}
            </div>
          ))}
        </div>
      </Sider>
      <Content style={{ padding: '24px', overflowY: 'auto', background: '#fafafa', flex: 1, minWidth: 0 }}>
        <div style={{maxWidth: 900, margin: '0 auto'}}>
            <div style={{display:'flex', justifyContent:'space-between', alignItems: 'center', marginBottom:24}}>
                <Title level={4} style={{margin:0}}>Transcript Viewer</Title>
                <Popover content={aiSettingsContent} title="AI Settings" trigger="click" open={popoverOpen} onOpenChange={setPopoverOpen}>
                    <Button type="primary" icon={<RobotOutlined />}>Run AI Analysis</Button>
                </Popover>
            </div>
            {renderMainContent()}
        </div>
      </Content>
    </Layout>
  );
};

export default TranscriptViewer;