import { useCallback, useEffect } from 'react';
import { useAppSelector, useAppDispatch } from '@/store/AppStateStore';
import { setCurrentFrame, nextFrame, previousFrame } from '@/store/slices/playbackControlSlice';
import { useWebSocketContext } from '@/hooks/websocket-context/WebSocketContext';

export function useWebSocketFrameNavigation() {
    const dispatch = useAppDispatch();
    const { currentFrame, totalFrames, isPlaying } = useAppSelector(state => state.playbackControl);
    const { requestFrame, latestFrameData, isConnected } = useWebSocketContext();

    // Request the current frame when it changes
    useEffect(() => {
        if (isConnected && totalFrames > 0) {
            requestFrame(currentFrame);
        }
    }, [currentFrame, totalFrames, isConnected, requestFrame]);

    // Navigation functions
    const goToFrame = useCallback((frame: number) => {
        dispatch(setCurrentFrame(frame));
    }, [dispatch]);

    const goToNextFrame = useCallback(() => {
        dispatch(nextFrame());
    }, [dispatch]);

    const goToPreviousFrame = useCallback(() => {
        dispatch(previousFrame());
    }, [dispatch]);

    // Prefetch next frames
    useEffect(() => {
        if (isConnected && totalFrames > 0 && !isPlaying) {
            // Prefetch next 3 frames
            for (let i = 1; i <= 3; i++) {
                const nextFrameNum = currentFrame + i;
                if (nextFrameNum < totalFrames) {
                    setTimeout(() => {
                        requestFrame(nextFrameNum);
                    }, i * 50); // Stagger requests
                }
            }
        }
    }, [currentFrame, totalFrames, isConnected, requestFrame, isPlaying]);

    return {
        currentFrame,
        totalFrames,
        isPlaying,
        frames: latestFrameData?.frames || {},
        isLoading: !latestFrameData || latestFrameData.frame_number !== currentFrame,
        error: null,
        goToFrame,
        goToNextFrame,
        goToPreviousFrame,
    };
}