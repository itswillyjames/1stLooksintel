import { useState, useCallback } from 'react';
import { toast } from 'sonner';

export function useApiCall() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const execute = useCallback(async (apiCall, options = {}) => {
    const { 
      onSuccess, 
      onError, 
      successMessage,
      showSuccessToast = true,
      showErrorToast = true 
    } = options;

    setLoading(true);
    setError(null);

    try {
      const response = await apiCall();
      const data = response.data;
      
      if (showSuccessToast && successMessage) {
        // Support both string and function for successMessage
        const msg = typeof successMessage === 'function' 
          ? successMessage(data) 
          : successMessage;
        toast.success(msg);
      }
      
      if (onSuccess) {
        onSuccess(data);
      }
      
      return { success: true, data };
    } catch (err) {
      const errorData = err.response?.data || { detail: err.message };
      setError(errorData);
      
      if (showErrorToast) {
        const errorMsg = typeof errorData.detail === 'string' 
          ? errorData.detail 
          : 'An error occurred';
        toast.error(errorMsg);
      }
      
      if (onError) {
        onError(errorData);
      }
      
      return { success: false, error: errorData };
    } finally {
      setLoading(false);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return { loading, error, execute, clearError };
}

// Generate a unique idempotency key
export function generateIdempotencyKey() {
  return `ui-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}
