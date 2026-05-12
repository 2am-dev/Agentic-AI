import { create } from 'zustand';

interface AgentState {
  sessionId: string;
  logs: any[];
  files: string[];
  activeFile: string | null;
  fileContent: string;
  isProcessing: boolean;
  addLog: (log: any) => void;
  setProcessing: (status: boolean) => void;
  setFiles: (files: string[]) => void;
  setActiveFile: (file: string, content: string) => void;
}

export const useStore = create<AgentState>((set) => ({
  sessionId: crypto.randomUUID(),
  logs: [],
  files: [],
  activeFile: null,
  fileContent: '',
  isProcessing: false,
  addLog: (log) => set((state) => ({ logs: [...state.logs, log] })),
  setProcessing: (status) => set({ isProcessing: status }),
  setFiles: (files) => set({ files }),
  setActiveFile: (file, content) => set({ activeFile: file, fileContent: content }),
}));