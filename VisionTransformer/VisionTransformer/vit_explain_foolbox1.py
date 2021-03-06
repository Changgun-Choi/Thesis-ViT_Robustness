"https://jacobgil.github.io/deeplearning/vision-transformer-explainability"
#set PYTHONPATH="C:/Users/ChangGun Choi/Team Project/Thesis_Vision/VisionTransformer/VisionTransformer/VisionTransformer"
#cd C:/Users/ChangGun Choi/Team Project/Thesis_Vision/VisionTransformer/VisionTransformer/VisionTransformer
#python vit_explain_foolbox.py --model_name dino_xcit --attack_name LinfPGD --use_cuda --head_fusion "min" --discard_ratio 0.9 

"1. vit_rollout"
#python vit_explain.py --image_path "C:/Users/ChangGun Choi/Team Project/Thesis_Vision/VisionTransformer/VisionTransformer/VisionTransformer/vit_visualization/examples/input.png" --head_fusion "min" --discard_ratio 0.8 

"2. Gradient Attention Rollout for class specific explainability"
#python vit_explain.py --head_fusion "min" --discard_ratio 0.8 --category_index 243
# We can multiply the attention with the gradient of the target class output, and take the average among the attention heads 
# (while masking out negative attentions) to keep only attention that contributes to the target category (or categories).

"Different Attention Head fusion methods"
"Removing the lowest attentions"

import os
os.chdir('C:/Users/ChangGun Choi/Team Project/Thesis_Vision/VisionTransformer/VisionTransformer/VisionTransformer')
import argparse
import torch
from PIL import Image
from torchvision import transforms
import numpy as np
import matplotlib.pyplot as plt
import cv2
from pathlib import Path
from attacks import *                                                                                                                                           
## 
from models import *
from models import VisionTransformer
from vit_rollout import VITAttentionRollout
from vit_grad_rollout import VITAttentionGradRollout
####
##
import torchvision.models as models
import torch
import eagerpy as ep
from foolbox import PyTorchModel, accuracy, samples
from foolbox.attacks import LinfPGD
from pytorch_pretrained_vit import ViT

#%%
def get_args(): 
    if args.use_cuda:
        print("Using GPU")
    else:
        print("Using CPU")
    return args

def show_mask_on_image(img, mask):
    img = np.float32(img) / 255
    heatmap = cv2.applyColorMap(np.uint8(255 * mask), cv2.COLORMAP_JET)
    heatmap = np.float32(heatmap) / 255
    cam = heatmap + np.float32(img)
    cam = cam / np.max(cam)
    return np.uint8(255 * cam)

if __name__ == '__main__':
    parser = argparse.ArgumentParser() 
    parser.add_argument('--attack_name', default='LinfPGD', type=str, help='attack name') 
    parser.add_argument('--model_name', default='deit', type=str, help='data name') 
    parser.add_argument('--use_cuda', action='store_true', default=False,
                        help='Use NVIDIA GPU acceleration')
    parser.add_argument('--image_path', type=str, default='./vit_visualization/input.png',
                        help='Input image path')
    parser.add_argument('--head_fusion', type=str, default='max',
                        help='How to fuse the attention heads for attention rollout. \
                        Can be mean/max/min')  # mean/max/min
    parser.add_argument('--discard_ratio', type=float, default=0.9,
                        help='How many of the lowest 14x14 attention paths should we discard')
    parser.add_argument('--category_index', type=int, default=None,
                        help='The category index for gradient rollout')
    "If category_index isn't specified, Attention Rollout will be used"
   
    args = parser.parse_args()
    #args.use_cuda = args.use_cuda and torch.cuda.is_available()
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu") 
    args.image_path = "C:/Users/ChangGun Choi/Team Project/Thesis_Vision/VisionTransformer/VisionTransformer/VisionTransformer/vit_visualization/examples/input.png"
    
    #%%
    if args.model_name == 'resnet50':  #  result = torch.eye(attentions[0].size(-1))  #IndexError: list index out of range
        model = torch.hub.load('facebookresearch/dino:main', 'dino_resnet50',pretrained=True).eval().to(device) # eval
    # elif args.model_name == 'efficientnet': 
    #    model = torch.hub.load('NVIDIA/DeepLearningExamples:torchhub', 'nvidia_efficientnet_b0', pretrained=True).eval().to(device)

    elif args.model_name == 'vit_B_16_imagenet1k': # RuntimeError: The size of tensor a (197) must match the size of tensor b (577) at non-singleton dimension 1
        model = ViT('B_16_imagenet1k', pretrained=True).eval().to(device)   # ??????:  Size??? ??????:: resize((384, 384))
        
    elif args.model_name == 'deit': # DeiT (Data-Efficient Image Transformers)
        model = torch.hub.load('facebookresearch/deit:main', 'deit_base_patch16_224', pretrained=True).eval().to(device)        
    #elif args.model_name =='deit_distilled': # RuntimeError: Cannot find callable deit_base_distilled_patch16_224 in hubconf
    #    model = torch.hub.load('facebookresearch/deit:main','deit_base_distilled_patch16_224').eval().to(device)       
        "self-supervised training of Vision Transformers"
    elif args.model_name == 'dino_vit': 
        model = torch.hub.load('facebookresearch/dino:main', 'dino_vitb16').eval().to(device)
 

    if args.use_cuda:
        model = model.cuda()
#%%
    preprocessing = dict(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225], axis=-3)
    fmodel = PyTorchModel(model, bounds=(0, 1), preprocessing=preprocessing)
    #images, labels = ep.astensors(*samples(fmodel, dataset="imagenet", batchsize=16))  ############### Batchsize = 1 for Explain
    
    
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
    ])
    img = Image.open(args.image_path)
    img = img.resize((224, 224))
    images = transform(img).unsqueeze(0)
    
    "label is added"
    labels = torch.tensor([243])             #Dog (category 243)
    
    if args.use_cuda:
        images = images.cuda() # RuntimeError: Expected all tensors to be on the same device, but found at least two devices, cuda:0 and cpu!
        labels = labels.cuda()
    #clean_acc = accuracy(fmodel, images, labels)
    #print(f"clean accuracy:  {clean_acc * 100:.1f} %")
    # apply the attack
    attack = LinfPGD()
    epsilons = [0, .05, .1, .15, .2, .25, .3]  # 7
    #%% "Attack" 
    #######################################################################################################################
    if args.attack_name == 'LinfPGD':  # single adversarial attack (Linf PGD)
        #images, labels = ep.astensors(*samples(fmodel, dataset="imagenet", batchsize=1))  ############### Batchsize = 1 for Explain
        attack = LinfPGD()
        print("epsilons")
        print(epsilons)
        #success
        raw_advs, clipped_advs, success = attack(fmodel, images, labels, epsilons=epsilons)
        # calculate and report the robust accuracy (the accuracy of the model when it is attacked)
       # robust_accuracy = 1 - success.float32().mean(axis=-1) # succes of Attack
       # print("robust accuracy for perturbations with")
       # for eps, acc in zip(epsilons, robust_accuracy):
       #     print(f"  Linf norm ??? {eps:<6}: {acc.item() * 100:4.1f} %")
#%%
        "clipped_advs"
        # we would need to check if the perturbation sizes are actually within the specified epsilon bound
        #print("robust accuracy for perturbations with")
        for epsilon, advs_ in zip(epsilons, clipped_advs):   # clipped_advs #######################################################
            #acc2 = accuracy(fmodel, advs_, labels) 
            #print(f"  Linf norm ??? {epsilon:<6}: {acc2 * 100:4.1f} %")
            #print("    perturbation sizes:")
            #perturbation_sizes = (advs_ - images).norms.linf(axis=(1, 2, 3)).numpy()
            #print("    ", str(perturbation_sizes).replace("\n", "\n" + "    "))
            #if acc2 == 0:
            #    break
##############################################################################################################
            original_img_view = images.squeeze(0).detach().cpu()
            original_img_view = original_img_view.transpose(0,2).transpose(0,1).numpy()
            "clipped_advs"
            perturbed_data = advs_ 
            perturbed_data_view = perturbed_data.squeeze(0).detach().cpu()
            perturbed_data_view = perturbed_data_view.transpose(0,2).transpose(0,1).numpy()
        
            #plt.imshow(perturbed_data_view)
        
            # ## ????????? ????????? ?????? ??????
            f, a = plt.subplots(1, 2, figsize=(10, 10))
            # ??????
            #a[0].set_title(prediction_name)
            a[0].imshow(original_img_view)
        
            # ????????? ??????
            #a[1].set_title(perturbed_prediction_name)
            a[1].imshow(perturbed_data_view)
            plt.show()
            
            
            
            "Original Roll_out"
           # perturbed_data    
            if args.category_index is None:          # "If category_index isn't specified, Attention Rollout will be used"
                print("Doing Attention Rollout")
                #attention_rollout = VITAttentionRollout(model, head_fusion=args.head_fusion, discard_ratio=args.discard_ratio)
                #mask = attention_rollout(perturbed_data)
                
                attention_rollout = VITAttentionRollout(model, head_fusion=args.head_fusion, discard_ratio=args.discard_ratio)
                mask = attention_rollout(perturbed_data) ###############
                
                name = "attention_rollout_{}_{:.3f}_{}_{}.png".format(args.model_name, args.discard_ratio, args.head_fusion, epsilon)
            else:
                print("Doing Gradient Attention Rollout")
                grad_rollout = VITAttentionGradRollout(model, discard_ratio=args.discard_ratio)
                mask = grad_rollout(perturbed_data, args.category_index)
                name = "grad_rollout_{}_{}_{:.3f}_{}_{}.png".format(args.model_name, args.category_index, args.discard_ratio, args.head_fusion, epsilon)

            # Roll_out for Adversal Examples
            
            np_img = np.array(img)[:, :, ::-1]
            mask = cv2.resize(mask, (np_img.shape[1], np_img.shape[0]))
            mask = show_mask_on_image(np_img, mask)
            #cv2.imshow("Input Image", np_img)
            cv2.imshow(name, mask)
            #cv2.imwrite("input.png", np_img)
            cv2.imwrite("C:/Users/ChangGun Choi/Team Project/Thesis_Vision/VisionTransformer/VisionTransformer/VisionTransformer/results"+ " " + name, mask)
            #"./vit_visualization"+ " " + name
            cv2.waitKey(-1)
#%%
    elif args.attack_name == 'multiple_attacks': 
        #images, labels = ep.astensors(*samples(fmodel, dataset="imagenet", batchsize=1))  ############### Batchsize = 1 for Explain
        attacks = [
            fa.FGSM(),   # FGSM= LinfFastGradientAttack(LinfBaseGradientDescent)
            fa.LinfPGD(),
            fa.LinfBasicIterativeAttack(),
            fa.LinfAdditiveUniformNoiseAttack(),
            fa.LinfDeepFoolAttack(),]
        print("epsilons")
        print(epsilons)
        print("")
        
        "attack:List"
        attack_success = np.zeros((len(attacks), len(epsilons), len(images)), dtype=np.bool)
        for i, attack in enumerate(attacks):
            _, _, success = attack(fmodel, images, labels, epsilons=epsilons)
            assert success.shape == (len(epsilons), len(images))
            success_ = success.numpy()
            assert success_.dtype == np.bool
            attack_success[i] = success_
            print(attack)
            print("  ", 1.0 - success_.mean(axis=-1).round(2))
    
        # calculate and report the robust accuracy (the accuracy of the model when
        # it is attacked) using the best attack per sample
        robust_accuracy = 1.0 - attack_success.max(axis=0).mean(axis=-1)
        print("")
        print("-" * 79)
        print("")
        print("worst case (best attack per-sample)")
        print("  ", robust_accuracy.round(2))
        print("")
    
        print("robust accuracy for perturbations with")
        for eps, acc in zip(epsilons, robust_accuracy):
            print(f"  Linf norm ??? {eps:<6}: {acc.item() * 100:4.1f} %")
            
        "VIT_Explain part"
        # ???????????? ?????? ????????? ?????? ??????            

        original_img_view = img_tensor.squeeze(0).detach().cpu()
        original_img_view = original_img_view.transpose(0,2).transpose(0,1).numpy()
        
        perturbed_data = fgsm_attack(img_tensor, epsilon, gradient) 
        perturbed_data_view = perturbed_data.squeeze(0).detach().cpu()
        perturbed_data_view = perturbed_data_view.transpose(0,2).transpose(0,1).numpy()
    
        #plt.imshow(perturbed_data_view)
    
        # ## ????????? ????????? ?????? ??????
        f, a = plt.subplots(1, 2, figsize=(10, 10))
        # ??????
        #a[0].set_title(prediction_name)
        a[0].imshow(original_img_view)
    
        # ????????? ??????
        #a[1].set_title(perturbed_prediction_name)
        a[1].imshow(perturbed_data_view)
        plt.show()
        
        "Original Roll_out"
       # perturbed_data    
        if args.category_index is None:          # "If category_index isn't specified, Attention Rollout will be used"
            print("Doing Attention Rollout")
            #attention_rollout = VITAttentionRollout(model, head_fusion=args.head_fusion, discard_ratio=args.discard_ratio)
            #mask = attention_rollout(perturbed_data)
            
            attention_rollout = VITAttentionRollout(model, head_fusion=args.head_fusion, discard_ratio=args.discard_ratio)
            mask = attention_rollout(perturbed_data) ###############
            
            name = "attention_rollout_{}_{:.3f}_{}_{}.png".format(args.model_name, args.discard_ratio, args.head_fusion, epsilon)
        else:
            print("Doing Gradient Attention Rollout")
            grad_rollout = VITAttentionGradRollout(model, discard_ratio=args.discard_ratio)
            mask = grad_rollout(perturbed_data, args.category_index)
            name = "grad_rollout_{}_{}_{:.3f}_{}_{}.png".format(args.model_name, args.category_index, args.discard_ratio, args.head_fusion, epsilon)

        # Roll_out for Adversal Examples
        
        np_img = np.array(img)[:, :, ::-1]
        mask = cv2.resize(mask, (np_img.shape[1], np_img.shape[0]))
        mask = show_mask_on_image(np_img, mask)
        #cv2.imshow("Input Image", np_img)
        cv2.imshow(name, mask)
        #cv2.imwrite("input.png", np_img)
        cv2.imwrite("C:/Users/ChangGun Choi/Team Project/Thesis_Vision/VisionTransformer/VisionTransformer/VisionTransformer/vit_visualization/"+ " " + name, mask)
        "./vit_visualization"+ " " + name
        cv2.waitKey(-1)

#RuntimeError: The size of tensor a (197) must match the size of tensor b (577) at non-singleton dimension 1