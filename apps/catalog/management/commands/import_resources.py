import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.catalog.models import ResourceItem

class Command(BaseCommand):
    help = 'Importa dados dos 4 JSONs (tecnologias, estrategias, materiais, abordagens)'

    def handle(self, *args, **kwargs):
        file_mapping = {
            'tecnologias.json': 'TA',
            'estrategias.json': 'EP',
            'materiais.json': 'MDA',
            'abordagens.json': 'MI'
        }

        data_dir = os.path.join(settings.BASE_DIR, 'data')

        registros_criados = 0
        registros_atualizados = 0

        for filename, category_code in file_mapping.items():
            filepath = os.path.join(data_dir, filename)
            
            if not os.path.exists(filepath):
                self.stderr.write(self.style.WARNING(f'Arquivo não encontrado: {filepath}. Pulando...'))
                continue
            
            with open(filepath, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    self.stderr.write(self.style.ERROR(f'O arquivo {filename} não é um JSON válido.'))
                    continue
                
            for perfil_pcd, lista_itens in data.items():
                for item_text in lista_itens:
                    if ':' in item_text:
                        nome, descricao = item_text.split(':', 1)
                        nome = nome.strip()
                        descricao = descricao.strip()
                    else:
                        nome = item_text.strip()
                        descricao = ""

                    obj, created = ResourceItem.objects.get_or_create(
                        name=nome,
                        category=category_code,
                        defaults={
                            'description': descricao,
                            'metadata_tags': [perfil_pcd]
                        }
                    )

                    if created:
                        registros_criados += 1
                    else:
                        if perfil_pcd not in obj.metadata_tags:
                            obj.metadata_tags.append(perfil_pcd)
                            obj.save()
                        registros_atualizados += 1

        self.stdout.write(self.style.SUCCESS(
            f'Importação inteligente concluída! {registros_criados} itens novos criados. {registros_atualizados} tags/itens atualizados.'
        ))