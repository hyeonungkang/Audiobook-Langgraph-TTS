const API_BASE = '/api/v1';

export interface ConvertConfig {
  language: string;
  category: string;
  narrative_mode: string;
  voice: string;
  listener_name: string;
  use_flash_lite?: boolean;
}

export interface ConvertRequest {
  text: string;
  config: ConvertConfig;
}

export interface JobStatus {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress?: number;
  current_step?: string;
  result?: {
    audio_path?: string;
    output_dir?: string;
    audio_title?: string;
    download_url?: string;
  };
  error?: string;
  created_at?: string;
  updated_at?: string;
}

export interface Voice {
  id: string;
  name: string;
  gender: string;
}

export interface Mode {
  id: string;
  name: string;
  description: string;
}

export const api = {
  async healthCheck(): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE.replace('/api/v1', '')}/health`);
    return res.json();
  },

  async getVoices(): Promise<{ voices: Voice[] }> {
    const res = await fetch(`${API_BASE}/voices`);
    return res.json();
  },

  async getModes(): Promise<{ modes: Mode[] }> {
    const res = await fetch(`${API_BASE}/modes`);
    return res.json();
  },

  async startConvert(request: ConvertRequest): Promise<{ job_id: string; status: string }> {
    const res = await fetch(`${API_BASE}/convert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || 'Failed to start conversion');
    }
    return res.json();
  },

  async getJobStatus(jobId: string): Promise<JobStatus> {
    const res = await fetch(`${API_BASE}/convert/${jobId}/status`);
    if (!res.ok) {
      throw new Error('Failed to get job status');
    }
    return res.json();
  },

  getDownloadUrl(filename: string): string {
    return `${API_BASE}/outputs/${filename}`;
  },
};
