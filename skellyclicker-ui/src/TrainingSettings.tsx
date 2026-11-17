import {AnchoredInfo} from '@freemocap/ui';

export const newModelLabel = 'New model · ResNet-50 GN (ImageNet-1K)';

export function StartingModelHelp() {
  return <AnchoredInfo title="Starting weights" text="For your first run, DeepLabCut starts with image features learned by ResNet-50 GN on ImageNet-1K and learns your keypoint locations from the labels. Choose a saved run to start from the keypoint weights you already trained."/>;
}

