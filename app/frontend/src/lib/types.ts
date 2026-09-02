export interface AppConfig {
  user: string;
  connections: { genie: boolean; ka: boolean; forecast: boolean; lakebase: boolean };
  forecastEndpoint: string;
  forecastBaseYear: number;
  lakebaseInstance: string;
  pgAppDb: string;
  segments: string[];
  sampleQuestions: string[];
  sampleDocQuestions: string[];
}

export interface GenieResult {
  answerText: string;
  generatedSql: string | null;
  columns: string[];
  rows: string[][];
  conversationId: string;
  messageId: string;
  logged?: boolean;
  logError?: string | null;
  error?: string;
}

export interface ChatTurn {
  question: string;
  result?: GenieResult;
  answer?: string; // docs tab
  pending?: boolean;
  error?: string;
}

export interface ForecastData {
  history: { segment: string; month: string; cases: number | null }[] | null;
  forecast: { segment: string; month: string; forecastCases: number | null }[] | null;
  segments: string[];
  endpointSet: boolean;
  lakebase: boolean;
}

export interface Scenario {
  createdAt: string;
  createdBy: string;
  segment: string;
  lag1: number;
  lag2: number;
  lag3: number;
  targetMonth: number;
  predictedCases: number | null;
}

export interface PredictResult {
  prediction: number;
  features: Record<string, number | string>;
  saved: boolean;
  saveError?: string | null;
  error?: string;
}

export interface ActionItem {
  id: number;
  title: string;
  note: string | null;
  status: string;
  createdBy: string;
  createdAt: string;
}

export interface DistributorsData {
  columns: string[];
  rows: Record<string, any>[];
  table?: string;
  pk?: string;
  error?: string;
}
