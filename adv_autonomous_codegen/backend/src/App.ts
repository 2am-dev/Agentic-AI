import React, { useEffect, useState, useRef } from 'react';
import { useStore } from './store';
import Editor from '@monaco-editor/react';
import { Play, Square, Terminal, FileCode2, Settings } from 'lucide-react';

export default function App() {
  const { sessionId, logs, addLog, isProcessing, setProcessing, files, setFiles, activeFile, fileContent, setActiveFile } = useStore();
  const [task, setTask] = useState('');
  const ws = useRef<WebSocket | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    ws.current = new WebSocket(`ws://localhost:8000/ws/${sessionId}`);
    
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'token') {
        // Handle streaming token logic (simplified for space: append to latest log)
        addLog({ type: 'stream', content: data.content, id: Date.now() });
      } else {
        addLog(data);
      }

      if (data.type === 'complete' || data.type === 'error' || data.type === 'terminated') {
        setProcessing(false);
      }
      if (data.type === 'tool_result' && data.tool === 'list_files') {
        try { setFiles(JSON.parse(data.result)); } catch(e){}
      }
    };

    return () => ws.current?.close();
  }, [sessionId]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const startTask = () => {
    setProcessing(true);
    ws.current?.send(JSON.stringify({ command: 'start_task', task, model: 'llama3', max_iterations: 15 }));
  };

  const loadFile = async (filename: string) => {
    const res = await fetch(`http://localhost:8000/files/${sessionId}/${filename}`);
    const data = await res.json();
    setActiveFile(filename, data.content || data.error);
  };

  return (
    <div className="flex h-screen bg-gray-900 text-gray-100 font-sans">
      
      {/* Sidebar */}
      <div className="w-80 bg-gray-800 border-r border-gray-700 flex flex-col">
        <div className="p-4 border-b border-gray-700">
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Terminal size={24} className="text-blue-400"/> AutoCoder
          </h1>
        </div>
        
        <div className="p-4 flex-1 flex flex-col gap-4">
          <textarea 
            className="w-full bg-gray-900 border border-gray-700 rounded p-3 text-sm focus:border-blue-500 outline-none resize-none h-32"
            placeholder="Describe the application you want to build..."
            value={task}
            onChange={(e) => setTask(e.target.value)}
          />
          <button 
            onClick={startTask}
            disabled={isProcessing || !task}
            className={`flex items-center justify-center gap-2 py-2 rounded font-medium transition-colors ${isProcessing ? 'bg-gray-600 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'}`}
          >
            {isProcessing ? <Square size={16}/> : <Play size={16}/>}
            {isProcessing ? 'Agent Running...' : 'Deploy Agent'}
          </button>

          <div className="mt-4 flex-1 overflow-y-auto">
            <h3 className="text-xs font-semibold text-gray-400 uppercase mb-2 flex items-center gap-2">
              <FileCode2 size={14}/> Workspace Files
            </h3>
            <ul className="space-y-1">
              {files.map(f => (
                <li key={f} 
                    onClick={() => loadFile(f)}
                    className={`text-sm p-2 rounded cursor-pointer truncate ${activeFile === f ? 'bg-blue-900/50 text-blue-300' : 'hover:bg-gray-700'}`}>
                  {f}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Main Workspace */}
      <div className="flex-1 flex flex-col">
        
        {/* Code Editor */}
        <div className="flex-1 border-b border-gray-700 relative">
          {activeFile ? (
            <Editor
              height="100%"
              theme="vs-dark"
              path={activeFile}
              value={fileContent}
              options={{ readOnly: true, minimap: { enabled: false } }}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500">
              Select a file to view code
            </div>
          )}
        </div>

        {/* Agent Log Terminal */}
        <div className="h-64 bg-black p-4 overflow-y-auto font-mono text-sm">
          {logs.map((log, idx) => {
            if (log.type === 'tool_call') return (
               <div key={idx} className="text-yellow-400 mb-2">
                 ▶ Executing Tool: {log.tool} <br/>
                 <span className="text-gray-500">{JSON.stringify(log.input)}</span>
               </div>
            );
            if (log.type === 'tool_result') return (
               <div key={idx} className="text-green-400 mb-2 whitespace-pre-wrap">
                 ✓ Result: {log.result}
               </div>
            );
            if (log.type === 'llm_end') return (
               <div key={idx} className="text-blue-300 mb-4 whitespace-pre-wrap">
                 {log.full_response}
               </div>
            );
            return null;
          })}
          <div ref={logEndRef} />
        </div>

      </div>
    </div>
  );
}