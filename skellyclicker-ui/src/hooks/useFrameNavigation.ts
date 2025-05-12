import { useState, useCallback } from 'react';
import { useGetFramesQuery } from '@/services/clientApi';
import { useAppSelector } from '@/store/AppStateStore';

export function useFrameNavigation() {
    const [currentFrame, setCurrentFrame] = useState(0);
    const totalFrameCount = useAppSelector(state => state.playbackControl.totalFrames);

    const {
        data: framesData,
        isLoading: isLoadingFrames,
        isFetching: isFetchingFrames,
        error: framesError,
        refetch: refetchFrames
    } = useGetFramesQuery(currentFrame, {
        skip: totalFrameCount === 0
    });

    const goToNextFrame = useCallback(() => {
        if (currentFrame < totalFrameCount - 1) {
            setCurrentFrame(prev => prev + 1);
        }
    }, [currentFrame, totalFrameCount]);

    const goToPreviousFrame = useCallback(() => {
        if (currentFrame > 0) {
            setCurrentFrame(prev => prev - 1);
        }
    }, [currentFrame]);

    const goToFrame = useCallback((frameNumber: number) => {
        if (frameNumber >= 0 && frameNumber < totalFrameCount) {
            setCurrentFrame(frameNumber);
        }
    }, [totalFrameCount]);

    return {
        currentFrame,
        totalFrameCount,
        frames: framesData?.frames || {},
        isLoadingFrames,
        isFetchingFrames,
        framesError,
        refetchFrames,
        goToNextFrame,
        goToPreviousFrame,
        goToFrame
    };
}
