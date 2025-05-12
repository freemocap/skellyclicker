import { useCallback } from 'react';
import { useGetFramesQuery } from '@/services/clientApi';
import { useAppSelector, useAppDispatch } from '@/store/AppStateStore';
import { setCurrentFrame, nextFrame, previousFrame } from '@/store/slices/playbackControlSlice';

export function useFrameNavigation() {
    const dispatch = useAppDispatch();
    const { currentFrame, totalFrames, isPlaying } = useAppSelector(state => state.playbackControl);

    // Fetch the current frame data
    const {
        data: framesData,
        isLoading,
        isFetching,
        error
    } = useGetFramesQuery({ frameNumber: currentFrame }, {
        skip: totalFrames === 0
    });

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

    return {
        currentFrame,
        totalFrames,
        isPlaying,
        frames: framesData?.frames || {},
        isLoading,
        isFetching,
        error,
        goToFrame,
        goToNextFrame,
        goToPreviousFrame,
    };
}