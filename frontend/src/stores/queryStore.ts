import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import { QueryRequest, QueryResponse } from '@/types/api';

export interface QueryHistoryItem {
  id: string;
  request: QueryRequest;
  response: QueryResponse;
  timestamp: number;
}

export interface QueryStoreState {
  queryHistory: QueryHistoryItem[];
  currentQuery: string;
  setCurrentQuery: (value: string) => void;
  addToHistory: (request: QueryRequest, response: QueryResponse) => void;
  clearHistory: () => void;
}

const generateHistoryId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

export const useQueryStore = create<QueryStoreState>()(
  persist(
    (set) => ({
      queryHistory: [],
      currentQuery: '',
      setCurrentQuery: (value) => set({ currentQuery: value }),
      addToHistory: (request, response) =>
        set((state) => ({
          queryHistory: [
            { id: generateHistoryId(), request, response, timestamp: Date.now() },
            ...state.queryHistory,
          ].slice(0, 50),
        })),
      clearHistory: () => set({ queryHistory: [] }),
    }),
    {
      name: 'epip-query-history',
      partialize: (state) => ({ queryHistory: state.queryHistory }),
    }
  )
);
