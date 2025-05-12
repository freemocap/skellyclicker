import {useCallback, useEffect, useRef, useState} from 'react';
import {z} from 'zod';
import {addLog, LogRecordSchema} from "@/store/slices/logRecordsSlice";
import {useAppDispatch} from "@/store/AppStateStore";

const MAX_RECONNECT_ATTEMPTS = 30;

// Define schema for frame data messages
export const FrameDataSchema = z.object({
    type: z.literal('frame_data'),
    frame_number: z.number(),
    frames: z.record(z.string(), z.string()), // [video_name, base64_image]
});

export type FrameData = z.infer<typeof FrameDataSchema>;

export const useWebSocket = (wsUrl: string) => {
    const [isConnected, setIsConnected] = useState(false);
    const [websocket, setWebSocket] = useState<WebSocket | null>(null);
    const [connectAttempt, setConnectAttempt] = useState(0);
    const [latestFrameData, setLatestFrameData] = useState<FrameData | null>(null);
    const dispatch = useAppDispatch();

    const handleIncomingMessage = useCallback((event: MessageEvent) => {
        const data = event.data;
        if (data instanceof Blob) {
            data.text().then(text => {
                parseAndValidateMessage(text);
            }).catch(error => {
                console.error('Error reading Blob data:', error);
            });
        } else if (typeof data === 'string') {
            parseAndValidateMessage(data);
        }
    }, []);

    const parseAndValidateMessage = useCallback(async (data: string) => {
        try {
            const parsedData = JSON.parse(data);

            // Try to parse as frame data
            try {
                const frameData = FrameDataSchema.parse(parsedData);
                setLatestFrameData(frameData);
                return;
            } catch (e) {
                if (!(e instanceof z.ZodError)) throw e;
            }

            // Try to parse as log record
            try {
                const logRecord = LogRecordSchema.parse(parsedData);
                dispatch(addLog({
                    message: logRecord.msg,
                    formatted_message: logRecord.formatted_message,
                    severity: logRecord.levelname.toLowerCase() as any,
                    name: logRecord.name,
                    rawMessage: logRecord.msg,
                    args: logRecord.args,
                    pathname: logRecord.pathname,
                    filename: logRecord.filename,
                    module: logRecord.module,
                    lineNumber: logRecord.lineno,
                    functionName: logRecord.funcName,
                    threadName: logRecord.threadName,
                    thread: logRecord.thread,
                    processName: logRecord.processName,
                    process: logRecord.process,
                    stackTrace: logRecord.stack_info,
                    exc_info: logRecord.exc_info,
                    exc_text: logRecord.exc_text,
                    delta_t: logRecord.delta_t,
                }));
                return;
            } catch (e) {
                if (!(e instanceof z.ZodError)) throw e;
            }

            console.error('Message did not match any known schema. Message keys:', Object.keys(parsedData));
        } catch (e) {
            if (e instanceof z.ZodError) {
                console.error('Validation failed with errors:', JSON.stringify(e.errors, null, 2));
            } else {
                console.error(`Failed to parse websocket message: ${e}`);
            }
        }
    }, [dispatch]);

    const connect = useCallback(() => {
        if (websocket && websocket.readyState !== WebSocket.CLOSED) {
            return;
        }
        if (connectAttempt >= MAX_RECONNECT_ATTEMPTS) {
            console.error(`Max reconnection attempts reached. Could not connect to ${wsUrl}`);
            return;
        }
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            setIsConnected(true);
            setConnectAttempt(0);
            console.log(`Websocket is connected to url: ${wsUrl}`)
        };

        ws.onclose = () => {
            setIsConnected(false);
            setConnectAttempt(prev => prev + 1);
        };

        ws.onmessage = (event) => {
            handleIncomingMessage(event);
        };

        ws.onerror = (error) => {
            console.error('Websocket error:', error);
        };
        setWebSocket(ws);
    }, [wsUrl, websocket, connectAttempt, handleIncomingMessage]);

    const disconnect = useCallback(() => {
        if (websocket) {
            websocket.close();
            setWebSocket(null);
        }
    }, [websocket]);

    // Function to request a specific frame
    const requestFrame = useCallback((frameNumber: number) => {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(JSON.stringify({
                type: 'frame_request',
                frame_number: frameNumber
            }));
        }
    }, [websocket]);

    useEffect(() => {
        const timeout = setTimeout(() => {
            console.log(`Connecting (attempt #${connectAttempt + 1} of ${MAX_RECONNECT_ATTEMPTS}) to websocket at url: ${wsUrl}`);
            connect();
        }, Math.min(1000 * Math.pow(2, connectAttempt), 30000)); // exponential backoff

        return () => {
            clearTimeout(timeout);
        };
    }, [connect, connectAttempt, wsUrl]);

    return {
        isConnected,
        connect,
        disconnect,
        requestFrame,
        latestFrameData,
    };
};