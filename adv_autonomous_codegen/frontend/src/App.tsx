import React, { useEffect, useState, useRef } from 'react';
import { useStore } from './store';
import Editor from '@monaco-editor/react';
import { Play, Square, Terminal } from 'lucide-react';

export default function App() {
  const { sessionId, logs, addLog, isProcessing, setProcessing, files, setFiles, activeFile, fileContent, setActiveFile } = useStore();
  const [task, setTask] = useState('');
  const ws = useRef(null);
  const logEndRef = useRef(null);

  useEffect(() => {
    if (!sessionId) return;

    // Dynamically construct WebSocket URL using current host
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    const wsUrl = `${protocol}//${host}:8000/ws/${sessionId}`;
    console.log('Connecting to WebSocket:', wsUrl);
    
    const socket = new WebSocket(wsUrl);
    ws.current = socket;
    
    socket.onopen = () => {
      console.log('WebSocket connected');
      addLog({ type: 'info', content: 'Connected to agent' });
    };
    
    socket.onerror = (err) => {
      console.error('WebSocket error:', err);
      addLog({ type: 'error', content: `WebSocket connection failed - make sure backend is running on port 8000` });
      setProcessing(false);
    };
    
    socket.onclose = (event) => {
      console.log('WebSocket closed', event.code, event.reason);
      addLog({ type: 'error', content: `Connection closed (${event.code})` });
      setProcessing(false);
    };
    
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      addLog(data);
      if (['complete', 'error', 'terminated'].includes(data.type)) setProcessing(false);
      if (data.type === 'tool_result' && data.tool === 'list_files') {
        try { setFiles(JSON.parse(data.result)); } catch(e) { console.error(e); }
      }
    };
    
    return () => socket.close();
  }, [sessionId, addLog, setProcessing, setFiles]);

  const startTask = () => {
    if (!task) return;
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
      addLog({ type: 'error', content: 'WebSocket not connected. Please refresh and try again.' });
      return;
    }
    setProcessing(true);
    ws.current.send(JSON.stringify({ command: 'start_task', task, model: 'llama3' }));
  };

  const loadFile = async (name) => {
    try {
      const host = window.location.hostname;
      const res = await fetch(`http://${host}:8000/files/${sessionId}/${name}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setActiveFile(name, data.content || 'File empty');
    } catch (err) {
      setActiveFile(name, `Error loading file: ${err.message}`);
    }
  };

  return (
    <div className="flex h-screen bg-gray-900 text-gray-100 font-sans">
      <div className="w-80 bg-gray-800 border-r border-gray-700 flex flex-col">
        <div className="p-4 border-b border-gray-700 font-bold flex items-center gap-2 text-blue-400">
          <Terminal size={20}/> AI AGENT CODER
        </div>
        <div className="p-4 flex-1 flex flex-col gap-4">
          <textarea 
            className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-sm h-32 focus:ring-1 ring-blue-500 outline-none"
            placeholder="What should I build?"
            value={task}
            onChange={(e) => setTask(e.target.value)}
          />
          <button onClick={startTask} disabled={isProcessing} className="bg-blue-600 hover:bg-blue-700 py-2 rounded flex items-center justify-center gap-2">
            {isProcessing ? <Square size={16}/> : <Play size={16}/>} Start
          </button>
          <div className="mt-4">
            <h3 className="text-xs font-bold text-gray-500 uppercase mb-2">Files</h3>
            {files.map(f => (
              <div key={f} onClick={() => loadFile(f)} className="text-sm p-1 hover:bg-gray-700 cursor-pointer rounded truncate">
                {f}
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="flex-1 flex flex-col">
        <div className="flex-1 bg-gray-900">
          {activeFile ? (
            <Editor height="100%" theme="vs-dark" defaultLanguage="python" value={fileContent} options={{readOnly: true}} />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-600 italic">No file selected</div>
          )}
        </div>
        <div className="h-64 bg-black border-t border-gray-700 p-4 overflow-y-auto font-mono text-xs">
          {logs.map((l, i) => (
            <div key={i} className="mb-1">
              <span className="text-blue-500">[{l.type}]</span> {l.content || l.result || l.tool || ''}
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}