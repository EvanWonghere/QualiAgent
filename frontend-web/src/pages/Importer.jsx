// src/pages/Importer.jsx
import React, { useState } from 'react';
import { Upload, Button, Card, message, Typography, Steps, Result, Radio, Collapse, Alert, Tooltip, Input } from 'antd';
import { InboxOutlined, FileTextOutlined, SettingOutlined, QuestionCircleOutlined, CheckCircleOutlined } from '@ant-design/icons';
import axios from 'axios';
import { Link } from 'react-router-dom';

const { Dragger } = Upload;
const { Panel } = Collapse;

const Importer = () => {
  const [currentStep, setCurrentStep] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState(null);

  // 默认使用 "Standard" 模式，因为它现在最强
  const [splitMode, setSplitMode] = useState('speaker_simple');
  const [customRegex, setCustomRegex] = useState('');

  const handleUpload = async (options) => {
    const { file, onSuccess, onError } = options;
    const formData = new FormData();
    formData.append('file', file);

    // ✨ 明确传递 split_mode
    formData.append('split_mode', splitMode);

    // 只有在自定义时才传正则
    if (splitMode === 'custom' && customRegex) {
      formData.append('split_pattern', customRegex);
    }

    setUploading(true);
    try {
      const res = await axios.post('http://localhost:8000/import/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      setUploadedFile(res.data);
      message.success(`Success! Sliced into ${res.data.segments_count} segments.`);
      onSuccess("ok");
      setCurrentStep(1);
    } catch (err) {
      message.error("Upload failed.");
      onError(err);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: 40 }}>
      <Steps current={currentStep} items={[
        { title: 'Upload & Parse', icon: <InboxOutlined /> },
        { title: 'Done', icon: <CheckCircleOutlined /> },
      ]} style={{ marginBottom: 40 }} />

      {currentStep === 0 && (
        <Card title="Upload Transcript">

          <Collapse ghost style={{ marginBottom: 20 }} defaultActiveKey={['1']}>
            <Panel header={<span style={{color:'#1890ff'}}><SettingOutlined/> Parse Settings</span>} key="1">
              <div style={{ padding: '0 10px 10px' }}>
                <Alert
                  type="info"
                  showIcon
                  message="Formatting Guide"
                  description="Choose 'Standard Speaker' if your file looks like 'Name: Hello' or 'Name (00:00): Hello'."
                  style={{marginBottom:15}}
                />

                <Radio.Group onChange={e => setSplitMode(e.target.value)} value={splitMode} style={{display: 'flex', flexDirection: 'column', gap: 8}}>
                  <Radio value="speaker_simple">
                    <strong>Standard Speaker</strong> (Recommended)
                    <div style={{color:'#999', fontSize:12, marginLeft:24}}>
                      Works for: "A:", "张三：", "访谈者 (00:00):"
                    </div>
                  </Radio>
                  <Radio value="default">Auto Sentence Split (No Speaker Names)</Radio>
                  <Radio value="custom">Custom Regex</Radio>
                </Radio.Group>

                {splitMode === 'custom' && (
                   <Input
                      addonBefore="Regex"
                      value={customRegex}
                      onChange={e => setCustomRegex(e.target.value)}
                      style={{marginTop:10}}
                      placeholder="e.g. ^\[.+?\]"
                    />
                )}
              </div>
            </Panel>
          </Collapse>

          <Dragger customRequest={handleUpload} showUploadList={false} height={200}>
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">Click or drag transcript here</p>
          </Dragger>
        </Card>
      )}

      {currentStep === 1 && (
        <Result
          status="success"
          title="Uploaded & Parsed!"
          subTitle={`Sliced into ${uploadedFile?.segments_count} segments.`}
          extra={[
            <Link to="/viewer" key="view">
              <Button type="primary" size="large" icon={<FileTextOutlined />}>
                Go to Transcript Viewer
              </Button>
            </Link>,
            <Button key="again" onClick={() => setCurrentStep(0)}>Upload Another</Button>
          ]}
        />
      )}
    </div>
  );
};

export default Importer;