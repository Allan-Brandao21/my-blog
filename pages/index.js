import Head from 'next/head'
import Prismic from '@prismicio/client'
import styles from '../styles/Home.module.css'
import Card from '../components/Card'



export default function Home({posts}) {


  return (
    <div className={styles.container}>
      <Head>
        <title>Allan Brandão</title>
        <meta name="description" content="Blog de Allan Brandão" />
        <link rel="icon" href="/favicon.svg" />
      </Head>
      <h1 className={styles.title}>Bem vindo a meu blog</h1> 
      <section className={styles.cardSection}>
      {
        posts.map(post => <Card post={post} key={post.uid}/>)
      }
      </section>

    </div>
  )
}

export async function getStaticProps({params}) {
  const apiEndpoint = 'https://allan-blog.cdn.prismic.io/api/v2'
  const Client = Prismic.client(apiEndpoint, {})

  const data = await Client.query(
    Prismic.Predicates.at('document.type', 'blog_post'),
    { orderings: '[my.post.date desc]' }
  )

  const posts = data.results
  return {
    props: {
      posts,
      revalidade: 86400
    }
  }
}
