import { useCallback, useState } from 'react';
import { useLoadRecordingMutation, LoadRecordingResponse } from '@/services/clientApi';
import { setTotalFrames } from '@/store/slices/playbackControlSlice';
import { useDispatch } from 'react-redux';

export function useLoadRecording() {
    // Local state for recording information
    const [recordingInfo, setRecordingInfo] = useState<LoadRecordingResponse | null>(null);
    const dispatch = useDispatch();

    const [loadRecording, {
        isLoading: isLoadingRecording,
        isError: isLoadingError,
        error: loadingError
    }] = useLoadRecordingMutation();

    const handleLoadRecording = useCallback(async (recordingPath: string) => {
        try {
            const response = await loadRecording(recordingPath).unwrap();

            // Store the recording info in local state
            setRecordingInfo(response);
            dispatch(setTotalFrames(response.frame_count));

            return response;
        } catch (error) {
            console.error('Failed to load recording:', error);
            throw error;
        }
    }, [loadRecording]);

    return {
        recordingInfo,
        isLoadingRecording,
        isLoadingError,
        loadingError,
        loadRecording: handleLoadRecording
    };
}
