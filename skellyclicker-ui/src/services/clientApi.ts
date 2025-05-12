import {createApi, fetchBaseQuery} from '@reduxjs/toolkit/query/react';
import {z} from 'zod';

// Schema for frame image response
export const FramesResponseSchema = z.object({
    frame_number: z.number(),
    frames: z.record(z.string(), z.string()), // camera_id -> base64 image data
});
export type FramesResponse = z.infer<typeof FramesResponseSchema>;

export const LoadRecordingResponseSchema = z.object({
    recording_path: z.string(),
    recording_name: z.string(),
    video_paths: z.array(z.string()),
    frame_count: z.number(),
})

export type LoadRecordingResponse = z.infer<typeof LoadRecordingResponseSchema>;

export const clientApi = createApi({
    reducerPath: 'clientApi',
    baseQuery: fetchBaseQuery({baseUrl: 'http://localhost:8089'}),
    tagTypes: ['Frames'],
    endpoints: (builder) => ({
        getFrames: builder.query<FramesResponse, number>({
            query: (frameNumber) => `/videos/frames/${frameNumber}`,
            providesTags: ['Frames'],
            transformResponse: (response: unknown) => {
                try {
                    return FramesResponseSchema.parse(response);
                } catch (error) {
                    console.error('Failed to parse frames response:', error);
                    throw new Error('Invalid frames data received');
                }
            },
        }),

        // Load recording - this should be a mutation since it changes server state
        loadRecording: builder.mutation<LoadRecordingResponse, string>({
            query: (recordingPath) => ({
                url: '/session/load_recording',
                method: 'POST',
                body: { recording_path: recordingPath },
            }),
            invalidatesTags: [ 'Frames'],
            transformResponse: (response: unknown) => {
                try {
                    return LoadRecordingResponseSchema.parse(response);
                } catch (error) {
                    console.error('Failed to parse load recording response:', error);
                    throw new Error('Invalid load recording data received');
                }
            },
        }),
    }),
});
export const {useGetFramesQuery, useLoadRecordingMutation} = clientApi;
