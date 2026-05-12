import { create } from 'zustand';

export const useStore = create((set) => ({
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
